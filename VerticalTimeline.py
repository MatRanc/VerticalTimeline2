#Author-Thomas Axelsson
#Description-Provides a vertical timeline.

# This file is part of VerticalTimeline, a Fusion 360 add-in that
# provides a vertical timeline.
#
# Copyright (C) 2020  Thomas Axelsson
#
# This work is dual-licensed under GPL 3.0 (or any later version) and MIT.
# You can choose between one of them if you use this work.

# Put add-in folder in %appdata%\Autodesk\Autodesk Fusion 360\API\AddIns

# Tested against Fusion's bundled Python 3.12 runtime and the new (Qt) palette
# web browser. The legacy CEF browser is deprecated by Autodesk.

import adsk.core, adsk.fusion, adsk.cam, traceback

from collections import defaultdict
import json
import os
import sys
import threading

NAME = 'Vertical Timeline'
FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# Import relative path to avoid namespace pollution
from .thomasa88lib import utils
from .thomasa88lib import events
from .thomasa88lib import timeline
from .thomasa88lib import manifest
from .thomasa88lib import error

# Force modules to be fresh during development
import importlib
importlib.reload(thomasa88lib)
importlib.reload(thomasa88lib.events)
importlib.reload(thomasa88lib.timeline)
importlib.reload(thomasa88lib.manifest)
importlib.reload(thomasa88lib.error)

from . import icons
importlib.reload(icons)

ui = None
app = None
error_catcher = thomasa88lib.error.ErrorCatcher(msgbox_in_debug=False)
events_manager = thomasa88lib.events.EventsManager(error_catcher)
manifest = thomasa88lib.manifest.read()

html_ready = False

timeline_item_count = 0
timeline_marker_position = -1

# Debounce for the command-terminated refresh. commandTerminated fires in bursts
# (a camera pan/orbit gesture fires it repeatedly), and each invalidate() is a
# full O(N) timeline rebuild + DOM teardown — so a burst freezes large
# assemblies (issue #9). Collapse the burst into one refresh after activity
# settles. threading.Timer runs on a worker thread where the Fusion API is
# off-limits, so the timer only fires a custom event that marshals back to the
# main thread (refresh_event_handler) to do the real work.
REFRESH_EVENT_ID = 'thomasa88_verticalTimeline_refresh'
DEBOUNCE_SECONDS = 0.1
_refresh_timer = None
_refresh_lock = threading.Lock()

def schedule_refresh():
    # ponytail: 100ms trailing debounce; collapses commandTerminated bursts
    # (pan/orbit) into one refresh. Raise DEBOUNCE_SECONDS if it still stutters,
    # lower it if the refresh feels laggy.
    global _refresh_timer
    with _refresh_lock:
        if _refresh_timer:
            _refresh_timer.cancel()
        _refresh_timer = threading.Timer(DEBOUNCE_SECONDS, _fire_refresh)
        _refresh_timer.start()

def _fire_refresh():
    # Worker thread — only marshal to the main thread, no API calls here.
    app.fireCustomEvent(REFRESH_EVENT_ID)

def refresh_event_handler(args):
    # Main thread. invalidate() already guards on palette/html_ready, so a fire
    # that lands after the palette closed is harmless.
    invalidate()

# Highlight the timeline row matching the feature selected in Fusion's GUI.
# Best-effort: matching is based on entity identity. Set to False to disable.
HIGHLIGHT_GUI_SELECTION = True

# Cap for the live-entity highlight fallback (find_node_id_for_entity). That
# fallback does an obj.entity API call per timeline node; above this many nodes
# it freezes large assemblies — it ran on every viewport selection (e.g. the
# geometry picked at the start of a pan), the issue-#9 freeze. Past the cap we
# highlight via the O(1) token index only.
FALLBACK_SCAN_MAX_NODES = 250  # ponytail: unmeasured guess; lower if a file near this size still lags on selection

# The palette is on by default (#11); closing it with the window X hides it
# for this session only — the next Fusion start / add-in reload brings it back.
# Turning the add-in off for good is Fusion's Scripts-and-Add-Ins dialog
# (Shift+S), not an add-in setting.
palette_closed_by_user = False

TIMELINE_STATUS_OK = 0
TIMELINE_STATUS_PRODUCT_NOT_READY = 1
TIMELINE_STATUS_NOT_PARAMETRIC = 2

# Camera/navigation commands that fire commandTerminated but never change the
# timeline. FreeOrbitCommand + PanCommand confirmed on macOS via trace (issue #9);
# the rest are the standard Fusion view ids. Extend from a trace if a navigation
# gesture still triggers a refresh.
NAV_COMMAND_IDS = {
    'FreeOrbitCommand', 'OrbitCommand', 'PanCommand',
    'ZoomCommand', 'FitCommand',
}
# Commands command_terminated_handler ignores: navigation (above) plus the
# selection/commit chatter that doesn't alter the timeline either.
# FusionDragComponentsCommand fires on every joint-drag release (there is no
# separate drive-joint id — confirmed by trace, 2026-07-15); the drag is
# kinematic and never creates a timeline object itself (Capture Position
# arrives as its own command), so skipping it kills the per-drag rebuild.
SKIP_REFRESH_COMMAND_IDS = NAV_COMMAND_IDS | {
    'SelectCommand', 'CommitCommand', 'FusionDragComponentsCommand'}

def find_commands(substring):
    return [c.id for c in ui.commandDefinitions if substring in c.id.lower()]

def find_commands_by_resource_folder(folder):
    commands = []
    for c in ui.commandDefinitions:
        try:
            if folder in c.resourceFolder.lower():
                commands.append(c.id)
        except:
            pass
    return commands

# ui.commandDefinitions.itemById('').resourceFolder
# design.rootComponent.allOccurrences[0].component.sketches

def invalidate(send=True, clear=False):
    global timeline_item_count
    global timeline_marker_position
    global html_ready

    palette = ui.palettes.itemById('thomasa88_verticalTimelinePalette')

    if not palette or not html_ready:
        return

    message = ""
    features = []
    max_parents = 0
    if not clear:
        timeline_status, timeline = thomasa88lib.timeline.get_timeline()
        if timeline_status == TIMELINE_STATUS_OK:
            timeline_item_count = timeline.count
            timeline_marker_position = timeline.markerPosition
            features, max_parents = get_features(timeline)
        elif timeline_status == TIMELINE_STATUS_PRODUCT_NOT_READY:
            timeline_item_count = -1
            timeline_marker_position = -1
        elif timeline_status == TIMELINE_STATUS_NOT_PARAMETRIC:
            timeline_item_count = -1
            timeline_marker_position = -1
            message = "Design is not parametric"
        else:
            print("Unhandled timeline status:", timeline_status)

    # Identify the active document so the palette can remember each document's
    # scroll position and restore it when the user switches back.
    try:
        doc_id = app.activeDocument.name
    except Exception:
        doc_id = ''

    action = 'setTimeline'
    data = {
         'features': features,
         'max-parents': max_parents,
         'message': message,
         'menu-icons': icons.get_menu_icons(),
         'document': doc_id,
    }

    if not send:
        # Cannot do sendInfoToHTML inside the HTML event handler. We either have to use htmlArgs.returnData or
        # spawn a thread (does not seem very safe? Can we call into the event loop instead?).
        html_command = {'action': 'setTimeline', 'data': data}
        return html_command
    else:
        palette.sendInfoToHTML('setTimeline', json.dumps(data))

def marker_fastpath_command(target_node):
    '''Post-roll palette update without the O(N) rebuild (PERFORMANCE.md Tier 1
    #2). A roll leaves the feature set unchanged — only which rows are rolled
    back — and rollTo(False) parks the marker right after the target, so the
    rolled-back set is exactly the leaves after the target in display order.
    That is computed from the cached tree with zero Fusion API calls; the JS
    toggles row classes in place. A group header counts as rolled back when all
    of its leaves are. Returns None (caller falls back to a full invalidate)
    when the target cannot be located in the cache.

    Ceiling: any side effect of the recompute (a re-included feature turning
    errored, say) is not reflected until the next full refresh.'''
    if timeline_cache_tree is None or target_node is None:
        return None
    # Rolling onto a group parks the marker after its last feature.
    target = target_node
    while target.children:
        target = target.children[-1]
    if target.obj is None:
        return None

    rolled = []
    seen_target = [False]
    def walk(node):
        # Returns True when every leaf under node is rolled back.
        all_rolled = bool(node.children)
        for child in node.children:
            if child.children:
                child_rolled = walk(child)
                if child_rolled:
                    rolled.append(child.id)
                all_rolled = all_rolled and child_rolled
            else:
                if seen_target[0]:
                    rolled.append(child.id)
                else:
                    all_rolled = False
                if child is target:
                    seen_target[0] = True
        return all_rolled
    walk(timeline_cache_tree)
    if not seen_target[0]:
        return None
    return {'action': 'setMarker', 'data': {'rolled': rolled}}

def report_message(text):
    '''Report a non-fatal message to the user without a blocking message box.

    The text is logged to the Text Commands console and returned as an HTML
    command so the palette can show it as a transient, non-intrusive status.'''
    print(f'Vertical Timeline: {text}')
    return {'action': 'showMessage', 'data': {'message': text}}

class TimelineObjectNode:
    def __init__(self, obj, id):
        self.obj = obj
        self.id = id
        # The object's TimelineObject.index (-1 for groups/collapsed-group
        # members), taken for free from the flatten iteration position.
        self.timeline_index = -1
        self.children = []

timeline_cache_tree = None
timeline_cache_map = None
# native entityToken -> node id, built while we already hold each feature's
# entity. Lets active_selection_changed_handler map a GUI selection to a row
# with an O(1) lookup instead of an obj.entity API call per node on every click.
timeline_cache_entity_index = {}
# TimelineObject.index -> node id. Second O(1) selection-highlight route:
# entityToken strings are documented as non-stable (the same entity can yield
# different strings on different reads), so the token index can miss; the
# timeline position cannot drift within one cache generation.
timeline_cache_position_index = {}
def get_features(timeline):
    global timeline_cache_tree, timeline_cache_map
    flat_timeline = thomasa88lib.timeline.flatten_timeline(timeline)
    timeline_cache_tree, timeline_cache_map = build_timeline_tree(flat_timeline)
    timeline_cache_entity_index.clear()
    timeline_cache_position_index.clear()
    timeline_cache_position_index.update(
        (node.timeline_index, node.id)
        for node in timeline_cache_map.values() if node.timeline_index >= 0)

    component_parent_map = get_cached_component_parent_map(timeline)
    design = app.activeProduct

    return get_features_from_node(timeline_cache_tree, component_parent_map, design)

# Component parent map cached across refreshes (PERFORMANCE.md Tier 2 #3): the
# map walk is O(occurrences) API calls, but component structure changes far
# less often than the timeline refreshes. Keyed on (document, timeline.count),
# so any add/delete (and a document switch) rebuilds it.
# ponytail: renaming or reparenting a component changes neither key, so the
# parent bars can show stale ancestry until the next add/delete; key on a
# rename/move signal if users notice.
_parent_map_cache = None
_parent_map_cache_key = None

def get_cached_component_parent_map(timeline):
    global _parent_map_cache, _parent_map_cache_key
    try:
        doc_name = app.activeDocument.name
    except Exception:
        doc_name = ''
    key = (doc_name, timeline.count)
    if _parent_map_cache is None or key != _parent_map_cache_key:
        _parent_map_cache = get_component_parent_map()
        _parent_map_cache_key = key
    return _parent_map_cache

def get_features_from_node(timeline_tree_node, component_parent_map, design):
    features = []
    max_parents = 0
    for i, child_node in enumerate(timeline_tree_node.children):
        obj = child_node.obj

        feature = {
            'id': str(child_node.id),
            'name': obj.name,
            'suppressed': obj.isSuppressed,
            'rolledBack': obj.isRolledBack,
            }

        # Health: surface error/warning state so the palette can highlight the
        # row (red/yellow). healthState lives on the timeline object itself (no
        # entity round-trip) and is Unknown for groups/snapshots. Best-effort:
        # never let it break the refresh while a document is tearing down.
        try:
            health = obj.healthState
            if health == adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState:
                feature['health'] = 'error'
                feature['health-message'] = obj.errorOrWarningMessage or ''
            elif health == adsk.fusion.FeatureHealthStates.WarningFeatureHealthState:
                feature['health'] = 'warning'
                feature['health-message'] = obj.errorOrWarningMessage or ''
        except Exception:
            pass

        # Might there be empty groups?
        if child_node.children:
            # Group
            feature['type'] = 'GROUP'
            icons.set_feature_image(feature, 'Fusion/UI/FusionUI/Resources/Timeline/GroupFeature')
            feature['children'], group_max_parents = get_features_from_node(child_node,
                                                                            component_parent_map,
                                                                            design)
            if group_max_parents > max_parents:
                max_parents = group_max_parents
        else:
            # Not group
            entity = entity_of(obj)
            
            if entity:
                feature_type = thomasa88lib.utils.short_class(entity)
                feature['type'] = feature_type

                # Index the native entity's token so GUI-selection highlighting
                # is an O(1) lookup. Best-effort: features whose token can't be
                # read are simply not matchable, same as before.
                native = native_of(entity)
                try:
                    timeline_cache_entity_index[native.entityToken] = child_node.id
                except Exception:
                    pass

                feature['image'], feature['imageDark'] = icons.get_feature_image(obj, entity, feature_type)
                # Parent-path resolution dips into .parent / .parentComponent /
                # .component on the live design, any of which can be missing or
                # inaccessible for a feature that is mid-removal or while a
                # document is closing. It is non-essential display metadata, so
                # degrade to no parent path rather than crashing the refresh.
                try:
                    parents = get_feature_parent_path(component_parent_map, obj,
                                                      entity, feature_type, design)
                except Exception:
                    parents = []
                feature['parent-components'] = parents
                if len(parents) > max_parents:
                    max_parents = len(parents)

                # Fully constrained sketches get Fusion's own lock-badge icon
                # (matching the browser), instead of the plain sketch icon.
                if feature_type == 'Sketch':
                    try:
                        if entity.isFullyConstrained:
                            if icons.get_first_image_path(icons.SKETCH_FULLY_CONSTRAINED_RES):
                                icons.set_feature_image(feature, icons.SKETCH_FULLY_CONSTRAINED_RES)
                    except Exception:
                        pass
                    # Current display-toggle states, so the right-click menu can
                    # label each item the way Fusion does ("Hide X" when shown,
                    # "Show X" when hidden).
                    for key, attr in (('profile', 'areProfilesShown'),
                                      ('dimension', 'areDimensionsShown'),
                                      ('projected', 'isProjectedGeometryShown'),
                                      ('construction', 'isConstructionGeometryShown')):
                        try:
                            feature['sk_' + key] = bool(getattr(entity, attr))
                        except Exception:
                            pass
            else:
                # Move and Align and more does not allow us to access their entity attribute
                # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/api-bug-cannot-access-entity-of-quot-move-quot-feature/m-p/9651921

                if obj.name.startswith('Derived from '):
                    feature['type'] = 'InsertDerive'
                    icons.set_feature_image(feature, 'Fusion/UI/FusionUI/Resources/Derive/CloneWM')
                else:
                    feature['type'] = '? (Feature info access prohibited by Fusion 360)'
                    icons.set_feature_image(feature, 'Fusion/UI/FusionUI/Resources/TSpline/Error')

            if feature['type'] == 'Occurrence':
                # Fusion uses a space separator for the timeline object name, but sometimes the first part is empty.
                # Strip the whitespace to make the list cleaner.
                feature['name'] = feature['name'].lstrip()
                try:
                    if thomasa88lib.timeline.get_occurrence_type(obj) not in icons.OCCURRENCE_PREFIXED_TYPES:
                        # Name is a read-only instance variant of the component's name,
                        # with a prefix on it.
                        # Let the user modify the component's name instead
                        feature['edit-name'] = obj.entity.component.name
                except Exception:
                    # The occurrence's component can be inaccessible mid-removal
                    # or while a document is closing. The editable name is
                    # optional, so just omit it rather than crashing the refresh.
                    pass

        features.append(feature)

    return (features, max_parents)

def get_feature_parent_path(component_parent_map, obj, entity=None, fusion_type=None, design=None):
    # entity / fusion_type / design are passed in on the hot refresh path to
    # avoid re-reading obj.entity, recomputing short_class, and fetching
    # app.activeProduct once per feature.
    if design is None:
        design = app.activeProduct

    feature = obj.entity if entity is None else entity
    feature_type = fusion_type if fusion_type is not None else thomasa88lib.utils.short_class(feature)
    if feature_type == 'Occurrence':
        if obj.isRolledBack or obj.isSuppressed:
            # No parent component will be available
            return []
        # The map is rebuilt fresh from the live occurrence tree, but the
        # timeline cache can still reference a component that is mid-removal
        # (command_terminated fires while the component is gone but the
        # timeline hasn't settled). Treat a missing component as no parent
        # path, same as the while loop below handles a missing parent.
        parent_name = component_parent_map.get(feature.component.name)
    elif feature_type == 'ConstructionPlane':
        if (feature.parent.classType() == 'adsk::fusion::Component' and
            feature.parent != design.rootComponent):
            parent_name = feature.parent.name
        else:
            return []
    elif not hasattr(feature, 'parentComponent'):
        if feature_type not in [ 'Snapshot' ]:
            print("Vertical Timeline: Unhandled missing parent for " + feature.classType())
        return []
    elif feature.parentComponent == design.rootComponent:
        return []
    else:
        parent_name = feature.parentComponent.name

    path = []
    while parent_name:
        path.append(parent_name)
        # If the parent component was suppressed or rolled back,
        # we won't find it, so stop in that case (get() will return None).
        parent_name = component_parent_map.get(parent_name)
    
    path.reverse()
    return path
    
    

def build_timeline_tree(flat_timeline):
    # The timeline tree returned from Fusion depends on the view state of
    # the GUI timeline control. Objects are grouped/nested only if a group
    # is collapsed in the GUI. Flatten the timeline to always get the same
    # result.

    next_id = 0
    def next_node_id():
        nonlocal next_id
        node_id = next_id
        next_id += 1
        return node_id

    def new_node(obj):
        node_id = next_node_id()
        node = TimelineObjectNode(obj, node_id)
        id_map[node_id] = node
        return node

    id_map = {}
    top_node = new_node(None)
    in_node = top_node
    group_nodes = [top_node]

    def get_group_node(group_obj):
        for group_node in group_nodes:
            if group_node.obj == group_obj:
                return group_node
        group_node = new_node(group_obj)
        group_nodes.append(group_node)
        parent_node = get_group_node(group_obj.parentGroup)
        parent_node.children.append(group_node)
        return group_node
    
    for obj, native_index in flat_timeline:
        node = new_node(obj)
        node.timeline_index = native_index
        parent_obj = obj.parentGroup
        if parent_obj != in_node.obj:
            in_node = get_group_node(parent_obj)
        in_node.children.append(node)

    return top_node, id_map

def get_component_parent_map():
    design = app.activeProduct
    component_parent_map = {}
    parent_map_occurrence(component_parent_map,
     None,
     design.rootComponent.occurrences)

    return component_parent_map

def parent_map_occurrence(component_parent_map, parent_name, occurrences):
    for occurrence in occurrences:
        name = occurrence.component.name
        component_parent_map[name] = parent_name
        parent_map_occurrence(component_parent_map,
         name,
         occurrence.childOccurrences)

def get_view_drop_down():
    qat = ui.toolbars.itemById('QAT')
    file_drop_down = qat.controls.itemById('FileSubMenuCommand')
    view_drop_down = file_drop_down.controls.itemById('ViewWidgetCommand')
    return view_drop_down

def get_active_workspace_id():
    '''Return the active workspace id, or None if there is no active environment.

    Reading ui.activeWorkspace can raise (RuntimeError:
    InternalValidationError : pActiveEnvironment) early at startup or on the
    Home screen, before any design environment is active. documentActivated can
    fire in that state, so callers must treat "no workspace" as a normal case
    rather than crashing.'''
    try:
        return ui.activeWorkspace.id
    except RuntimeError:
        return None

def run(context):
    global ui, app
    debug = False
    with error_catcher:
        app = adsk.core.Application.get()
        ui = app.userInterface

        events_manager.add_handler(ui.commandTerminated,
                    adsk.core.ApplicationCommandEventHandler,
                    command_terminated_handler)

        # Custom event used to debounce command_terminated_handler back onto the
        # main thread (see schedule_refresh).
        refresh_event = events_manager.register_event(REFRESH_EVENT_ID)
        events_manager.add_handler(refresh_event, callback=refresh_event_handler)

        # Edit command tracing
        # def f(args):
        #     print(args.commandId)
        #     args.isCanceled = True
        # events_manager.add_handler(ui.commandStarting,
        #             adsk.core.ApplicationCommandEventHandler,
        #             f)

        # Fusion bug: Activated is not called when switching to/from Drawing.
        # https://forums.autodesk.com/t5/fusion-360-api-and-scripts/api-bug-application-documentactivated-event-do-not-raise/m-p/9020750
        events_manager.add_handler(app.documentActivated,
                    adsk.core.DocumentEventHandler,
                    document_activated_handler)

        events_manager.add_handler(ui.workspacePreDeactivate,
                    adsk.core.WorkspaceEventHandler,
                    workspace_pre_deactivate_handler)

        events_manager.add_handler(ui.workspaceActivated,
                    adsk.core.WorkspaceEventHandler,
                    workspace_activated_handler)

        # Highlight in the palette whatever feature the user selects in the GUI.
        events_manager.add_handler(ui.activeSelectionChanged,
                    adsk.core.ActiveSelectionEventHandler,
                    active_selection_changed_handler)

        print("Running")

        # Show palette when user starts the add-in manually
        if app.isStartupComplete:
            show_palette()

def stop(context):
    with error_catcher:
        print('Stopping')

        if _refresh_timer:
            _refresh_timer.cancel()

        events_manager.clean_up()

        # Delete the palette created by this add-in.
        palette = ui.palettes.itemById('thomasa88_verticalTimelinePalette')
        if palette:
            palette.deleteMe()

        # The Toggle menu command was removed in #11; keep deleting any control/
        # command definition a previously-running version left behind.
        view_drop_down = get_view_drop_down()
        cntrl = view_drop_down.controls.itemById('thomasa88_showVerticalTimeline')
        if cntrl:
            cntrl.deleteMe()
        cmdDef = ui.commandDefinitions.itemById('thomasa88_showVerticalTimeline')
        if cmdDef:
            cmdDef.deleteMe()

def show_palette():
    global html_ready

    palette = ui.palettes.itemById('thomasa88_verticalTimelinePalette')
    if not palette:
        html_ready = False

        # useNewWebBrowser=True selects Fusion's new Qt-based palette browser.
        # Autodesk deprecated the legacy CEF browser and recommends opting in so
        # the add-in keeps working once CEF support is removed. With the new
        # browser adsk.fusionSendData() returns a Promise, which palette.html
        # handles via async/await.
        palette = ui.palettes.add('thomasa88_verticalTimelinePalette', 'Vertical Timeline',
                                    'palette.html',
                                    True, True, True, 250, 500, True)
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateLeft

        events_manager.add_handler(palette.incomingFromHTML,
                                   adsk.core.HTMLEventHandler,
                                   palette_incoming_from_html_handler)

        events_manager.add_handler(palette.closed,
                                   adsk.core.UserInterfaceGeneralEventHandler,
                                   palette_closed_handler)        
    else:
        invalidate()
        if not palette.isVisible:
            palette.isVisible = True

def hide_palette():
    palette = ui.palettes.itemById('thomasa88_verticalTimelinePalette')
    if palette:
        palette.isVisible = False

# Event handler for the palette close event.
def palette_closed_handler(args):
    global palette_closed_by_user
    palette_closed_by_user = True

def add_entity_to_collection(newSelection, entity, design):
    '''Add a timeline feature's entity (with its assembly-context proxies) to a
    selection collection. Returns True if the feature proxy itself was added (so
    it can be edited), False if only its produced bodies were added (a fallback
    that allows highlighting but not editing).'''
    if isinstance(entity, adsk.fusion.Occurrence):
        try:
            associated_component = entity.sourceComponent
        except RuntimeError:
            # A deleted/suppressed "component from bodies" occurrence has an
            # invalid path, so sourceComponent raises InternalValidationError
            # (path.valid()). Nothing to select - treat it as non-selectable.
            return True
    elif isinstance(entity, adsk.fusion.ConstructionPlane):
        associated_component = entity.parent
    elif hasattr(entity, 'parentComponent'):
        associated_component = entity.parentComponent
    else:
        # Some timeline entities (e.g. a position Snapshot / "capture position")
        # have no component and cannot be selected in the viewport. Add nothing;
        # callers treat an empty collection as "not selectable".
        return True

    if associated_component == design.rootComponent:
        # There are no occurrences of root - just the single root instance.
        # The entity can be selected directly.
        newSelection.add(entity)
        return True

    # The entity lives inside a component that may be instanced several times.
    # Select it in every occurrence context (allOccurrencesByComponent also
    # reaches nested occurrences).
    in_occurrences = design.rootComponent.allOccurrencesByComponent(associated_component)
    if hasattr(entity, 'createForAssemblyContext'):
        # Features, sketches, planes and occurrences support assembly-context
        # proxies. Selecting the feature proxy - not just its bodies - is what
        # lets the edit command operate on the feature.
        for occurrence in in_occurrences:
            newSelection.add(entity.createForAssemblyContext(occurrence))
        return True
    elif hasattr(entity, 'bodies'):
        # Fallback for entities with no assembly-context proxy: select the
        # produced bodies. The feature itself cannot be edited this way.
        for body in entity.bodies:
            for occurrence in in_occurrences:
                newSelection.add(body.createForAssemblyContext(occurrence))
        return False
    return True

def entity_of(obj):
    '''obj.entity, or None when Fusion refuses access (Move/Align, groups,
    document teardown all raise RuntimeError instead of returning the entity).'''
    try:
        return obj.entity
    except RuntimeError:
        return None

def native_of(entity):
    '''The underlying native object, or the entity itself if it has none.
    Assembly-context proxies often refuse edits/deletes; the native does not.'''
    return getattr(entity, 'nativeObject', None) or entity

def nodes_for(data):
    '''Valid cached nodes for a multi-select action, skipping ids that are stale
    (gone from the rebuilt cache) or have no timeline object.'''
    for i in data.get('ids', []):
        node = timeline_cache_map.get(i)
        if node and node.obj is not None:
            yield node

def _delete_entity(obj):
    '''Delete the model entity behind a (non-group) timeline object. Prefer the
    native object - deleting an assembly-context proxy is often refused.'''
    entity = obj.entity
    target = native_of(entity)
    return target.deleteMe()

def _delete_timeline_obj(obj):
    '''Delete a non-group timeline feature. TimelineObject has no deleteMe, so we
    delete its entity. A broken/suppressed body->component row has no computed
    occurrence, so its path is unresolvable and deleteMe() raises findObjectPath;
    force a recompute (end unsuppressed) and retry, restoring the original
    suppression state if the delete still fails so a failed attempt does not
    change the model.'''
    try:
        return _delete_entity(obj)
    except RuntimeError:
        # Only a broken/suppressed row (unresolvable occurrence path) can be
        # rescued by the recompute below. A healthy feature that refuses to
        # delete - e.g. one needed by a later feature - should surface as-is,
        # not get its suppression pointlessly toggled.
        try:
            broken = obj.isSuppressed or obj.healthState in (
                adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState,
                adsk.fusion.FeatureHealthStates.WarningFeatureHealthState)
        except (RuntimeError, AttributeError):
            broken = False
        if not broken:
            raise
    # ponytail: recompute + delete are two separate undo steps (not one atomic
    # transaction), and the recompute transiently rebuilds the feature. Wrap in
    # UndoManager / a timeline group if single-step undo ever matters.
    original = obj.isSuppressed
    try:
        if original:
            obj.isSuppressed = False          # unsuppress -> recompute the path
        else:
            obj.isSuppressed = True            # a broken but unsuppressed row:
            obj.isSuppressed = False           # toggle to force the recompute
        return _delete_entity(obj)
    except RuntimeError:
        try:
            obj.isSuppressed = original
        except (RuntimeError, AttributeError):
            pass
        raise

def _collect_group_contents(node):
    '''Split a group node's descendants into (leaf feature nodes, sub-group
    nodes). Sub-groups come out deepest-first so their now-empty shells can be
    removed inner-to-outer. Uses the already-materialized TimelineObjectNode tree
    so no timeline re-walk is needed.'''
    leaves, groups = [], []
    def walk(n):
        for child in n.children:
            if child.obj is not None and child.obj.isGroup:
                walk(child)
                groups.append(child)   # after its children -> deepest-first
            else:
                leaves.append(child)
    walk(node)
    return leaves, groups

def _delete_group_contents(node):
    '''Delete a timeline group AND its contents. Route each contained feature
    through _delete_timeline_obj - which handles broken body->component rows that
    Fusion's native recursive deleteMe(True) mishandles - then drop the emptied
    group shell(s).'''
    leaves, groups = _collect_group_contents(node)
    def _index(n):
        try:
            return n.obj.index
        except (RuntimeError, AttributeError):
            return -1
    # Delete later items first so removing one does not shift the timeline index
    # of the others (same ordering as the multi-select delete below).
    all_ok = True
    for leaf in sorted(leaves, key=_index, reverse=True):
        # deleteMe() returns False (no exception) for a feature Fusion refuses to
        # delete because it has downstream dependents - the API cannot show the
        # "may cause downstream issues" confirmation the native timeline delete
        # uses to force it. Track that so we report failure instead of silently
        # claiming success (which looked like "freezes, then nothing happens").
        try:
            if not _delete_timeline_obj(leaf.obj):
                all_ok = False
        except (RuntimeError, AttributeError):
            all_ok = False
    # Remove the emptied wrapper(s), innermost first. An emptied group may have
    # auto-vanished already - swallow that.
    for g in groups + [node]:
        try:
            g.obj.isCollapsed = True
            g.obj.deleteMe(False)
        except (RuntimeError, AttributeError):
            pass
    return all_ok

# Event handler for the palette HTML event.
def palette_incoming_from_html_handler(args):
    global html_ready
    htmlArgs = adsk.core.HTMLEventArgs.cast(args)
    action = htmlArgs.action
    data = json.loads(htmlArgs.data)
    html_commands = []

    # Single-item actions operate on a cached timeline node referenced by id.
    # That id comes from the last rendered palette; if the timeline changed
    # underneath us before the click arrived (external edit, undo, document
    # close), the id may no longer be in the freshly rebuilt cache. No-op the
    # stale click instead of raising a KeyError that pops an error dialog -
    # the palette refreshes itself anyway. The multi-item actions below already
    # skip missing nodes via timeline_cache_map.get(i).
    if action in ('setFeatureName', 'selectFeature', 'editFeature',
                  'rollToFeature', 'suppressFeature', 'deleteFeature',
                  'toggleVisibility', 'toggleSketchAttr',
                  'selectSketchPlane', 'runNativeCommand'):
        if timeline_cache_map is None or data['id'] not in timeline_cache_map:
            return

    if action == 'ready':
        print('HTML ready')
        html_ready = True

        # Cannot do sendInfoToHTML inside the event handler. We either have to use htmlArgs.returnData or
        # spawn a thread (does not seem very safe? Can we call into the event loop instead?).
        html_commands.append(invalidate(send=False))
    elif action == 'setFeatureName':
        node = timeline_cache_map[data['id']]
        obj = node.obj
        visible_name = None
        if data['value'] != '':
            entity = entity_of(obj)
            if (not obj.isGroup
                and entity
                and entity.classType() == 'adsk::fusion::Occurrence'
                and thomasa88lib.timeline.get_occurrence_type(obj) not in icons.OCCURRENCE_PREFIXED_TYPES):
                # Bonus of not doing a Command transaction: Undo history actually says from and to name.
                entity.component.name = data['value']
                # The shown name will have changed. Invalidate.
                #html_commands.append(invalidate(send=False))
            else:
                obj.name = data['value']
            visible_name = obj.name.lstrip()
        html_commands.append(visible_name)
    elif action == 'selectFeature' or action == 'editFeature':
        node = timeline_cache_map[data['id']]
        obj = node.obj
        ret = True

        design: adsk.fusion.Design = app.activeProduct

        entity = entity_of(obj)

        if entity is None:
            # Not an error - e.g. the user may just be clicking a group to
            # rename it. Only report when an edit was explicitly requested, and
            # never let entity access crash the handler.
            if action == 'editFeature':
                html_commands.append(report_message(
                    'This timeline item cannot be selected or edited.'))
                ret = False
        else:
            # Build the new selection in a transactory way, so the current selection
            # is not cleared if the entity turns out to be unselectable.
            newSelection = adsk.core.ObjectCollection.create()

            # add_entity_to_collection returns whether the feature itself was
            # added (editable) or only its produced bodies (highlight-only).
            editable = add_entity_to_collection(newSelection, entity, design)

            if newSelection.count == 0:
                # Nothing selectable (e.g. a position Snapshot, or a feature with
                # no produced bodies). Leave the current selection untouched;
                # only report when an edit was explicitly requested.
                if action == 'editFeature':
                    html_commands.append(report_message(
                        'This timeline item cannot be selected or edited.'))
                    ret = False
            else:
                try:
                    ui.activeSelections.all = newSelection
                except Exception as e:
                    html_commands.append(report_message(
                        f'Failed to select {thomasa88lib.utils.short_class(entity)}: {e}'))
                    ret = False

                if ret and action == 'editFeature':
                    command_id = icons.get_feature_edit_command_id(obj)
                    if not editable:
                        html_commands.append(report_message(
                            f'Editing {thomasa88lib.utils.short_class(entity)} inside a '
                            'component is not supported.'))
                        ret = False
                    elif command_id:
                        ui.commandDefinitions.itemById(command_id).execute()
                    else:
                        html_commands.append(report_message(
                            f'Editing {thomasa88lib.utils.short_class(entity)} feature is not supported.'))
                        ret = False

        html_commands.append(ret)
    elif action == 'selectFeatures':
        # Push a real multi-entity Fusion selection (so commands like Mirror can
        # consume the rows picked here), not just the palette's row highlight.
        design = app.activeProduct
        newSelection = adsk.core.ObjectCollection.create()
        for node in nodes_for(data):
            entity = entity_of(node.obj)
            if entity is None:
                continue
            try:
                add_entity_to_collection(newSelection, entity, design)
            except Exception:
                # Skip anything that can't be resolved; selecting the rest is
                # better than failing the whole pick.
                pass
        try:
            ui.activeSelections.all = newSelection
        except Exception as e:
            html_commands.append(report_message(f'Failed to select items: {e}'))
    elif action == 'rollToFeature':
        node = timeline_cache_map[data['id']]
        obj = node.obj
        if obj.isGroup and not obj.isCollapsed:
            # Cannot move to collapsed group.
            # Move to the last item of the group.
            obj = obj[-1]
        elif not obj.isGroup and obj.parentGroup and obj.parentGroup.isCollapsed:
            # The palette tracks its own group collapse state, so a group can be
            # open in the palette (child rows draggable) while still collapsed in
            # Fusion. Expand it in Fusion so the marker can land on this child,
            # instead of redirecting the roll to the whole group (which made the
            # marker only ever sit before/after the group).
            obj.parentGroup.isCollapsed = False
        rolled_ok = obj.rollTo(False)
        html_commands.append(rolled_ok)
        # A successful roll takes the in-place fast path (see
        # marker_fastpath_command); anything unexpected falls back to the full
        # rebuild, which is the correctness backstop.
        fastpath = marker_fastpath_command(node) if rolled_ok else None
        html_commands.append(fastpath or invalidate(send=False))
    elif action == 'toggleVisibility':
        # Show/Hide, mirroring the entity's browser-tree visibility toggle.
        # Different entity types expose it differently (isLightBulbOn for
        # occurrences/bodies/planes, isVisible for sketches), so try both.
        node = timeline_cache_map[data['id']]
        obj = node.obj
        entity = entity_of(obj)
        toggled = False
        for attr in ('isLightBulbOn', 'isVisible'):
            if entity is not None and hasattr(entity, attr):
                try:
                    setattr(entity, attr, not getattr(entity, attr))
                    toggled = True
                    break
                except (RuntimeError, AttributeError):
                    pass
        if not toggled:
            html_commands.append(report_message('Cannot show/hide this item.'))
        html_commands.append(invalidate(send=False))
    elif action == 'toggleSketchAttr':
        # Flip one of a sketch's display booleans (Hide/Show Profile, Dimension,
        # Projected/Construction Geometries). invalidate() refreshes the timeline
        # so the menu re-reads the new state and labels the item correctly next time.
        node = timeline_cache_map[data['id']]
        obj = node.obj
        attr = data.get('attr', '')
        entity = entity_of(obj)
        if entity is not None and hasattr(entity, attr):
            try:
                setattr(entity, attr, not getattr(entity, attr))
            except (RuntimeError, AttributeError) as e:
                html_commands.append(report_message(
                    f'Could not change this sketch display option: {e}'))
        else:
            html_commands.append(report_message('This option is not available for this item.'))
        html_commands.append(invalidate(send=False))
    elif action == 'selectSketchPlane':
        node = timeline_cache_map[data['id']]
        obj = node.obj
        entity = entity_of(obj)
        plane = getattr(entity, 'referencePlane', None)
        if plane:
            sel = adsk.core.ObjectCollection.create()
            sel.add(plane)
            try:
                ui.activeSelections.all = sel
            except Exception as e:
                html_commands.append(report_message(f'Could not select the sketch plane: {e}'))
        else:
            html_commands.append(report_message('This sketch has no selectable plane.'))
    elif action == 'runNativeCommand':
        # Select the feature first so the native command has its context, then
        # run Fusion's own command (found by its menu label). Reports back if the
        # command isn't available, so the menu item never silently does nothing.
        node = timeline_cache_map[data['id']]
        obj = node.obj
        cmd_name = data.get('name', '')
        design = app.activeProduct
        entity = entity_of(obj)
        if entity is not None:
            sel = adsk.core.ObjectCollection.create()
            try:
                add_entity_to_collection(sel, entity, design)
                if sel.count:
                    ui.activeSelections.all = sel
            except Exception:
                pass
        cmd_def = icons.find_command_def_by_name(cmd_name)
        if cmd_def:
            try:
                cmd_def.execute()
            except (RuntimeError, AttributeError) as e:
                html_commands.append(report_message(f'Could not run "{cmd_name}": {e}'))
        else:
            html_commands.append(report_message(
                f'"{cmd_name}" is not available for this item.'))
    elif action == 'suppressFeature':
        node = timeline_cache_map[data['id']]
        obj = node.obj
        new_state = not obj.isSuppressed
        try:
            obj.isSuppressed = new_state
        except (RuntimeError, AttributeError):
            html_commands.append(report_message(
                f'Cannot {"suppress" if new_state else "unsuppress"} this item.'))
        html_commands.append(invalidate(send=False))
    elif action == 'deleteFeature':
        node = timeline_cache_map[data['id']]
        obj = node.obj
        deleted = False
        type_name = 'item'
        err = ''
        try:
            if obj.isGroup:
                # Match Fusion's native "Group Delete" prompt: choose whether the
                # contents survive. deleteMe(False) keeps/expands them;
                # deleteMe(True) deletes them too.
                choice = ui.messageBox(
                    'Delete this timeline group?\n\n'
                    'Yes – Delete group and expand its contents\n'
                    'No – Delete both group and its contents\n'
                    'Cancel – Keep the group',
                    'Group Delete',
                    adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType,
                    adsk.core.MessageBoxIconTypes.QuestionIconType)
                if choice == adsk.core.DialogResults.DialogCancel:
                    deleted = True  # user backed out; nothing failed
                elif choice == adsk.core.DialogResults.DialogNo:
                    # Delete group + contents. Fusion's native deleteMe(True) can
                    # silently no-op here: when the contents have downstream
                    # dependents it would need the "permanently delete features"
                    # confirmation, which the API can't show, so it reports success
                    # without deleting. Delete each contained feature individually
                    # instead - it actually removes them (and handles a broken
                    # body->component row native chokes on). Ceiling: this is N
                    # separate operations, so it recomputes per feature (slow on
                    # big groups) and takes N undo steps rather than one; Fusion's
                    # scripting API exposes no way to batch them atomically.
                    deleted = _delete_group_contents(node)
                else:
                    # Delete group, keep/expand its contents. deleteMe acts on the
                    # group as a single collapsed timeline unit; an expanded group
                    # has no timeline index, so deleteMe throws. The palette can
                    # show a group still expanded in Fusion, so collapse it first
                    # (same workaround as rollToFeature above).
                    try:
                        obj.isCollapsed = True
                    except (RuntimeError, AttributeError):
                        pass
                    deleted = obj.deleteMe(False)
            else:
                type_name = thomasa88lib.utils.short_class(obj.entity)
                deleted = _delete_timeline_obj(obj)
        except (RuntimeError, AttributeError) as e:
            deleted = False
            err = str(e)
        if not deleted:
            reason = f': {err}' if err else ' (it may be needed by later features).'
            html_commands.append(report_message(
                f'Could not delete this {type_name}{reason}'))
        html_commands.append(invalidate(send=False))
    elif action == 'deleteAllAfterMarker':
        # Mirrors Fusion's native "Delete all features after History Marker"
        # (offered when right-clicking a rolled-back row).
        timeline_status, timeline = thomasa88lib.timeline.get_timeline()
        if timeline_status == TIMELINE_STATUS_OK:
            try:
                timeline.deleteAllAfterMarker()
            except (RuntimeError, AttributeError):
                html_commands.append(report_message(
                    'Could not delete the features after the marker.'))
        html_commands.append(invalidate(send=False))
    elif action == 'createGroup':
        # Fusion groups are a contiguous timeline range, so group everything
        # between the first and last selected items (inclusive).
        indices = []
        for node in nodes_for(data):
            try:
                indices.append(node.obj.index)
            except (RuntimeError, AttributeError):
                pass
        if len(indices) >= 2:
            try:
                app.activeProduct.timeline.timelineGroups.add(min(indices),
                                                              max(indices))
            except (RuntimeError, AttributeError):
                html_commands.append(report_message(
                    'Could not create a group from the selected items.'))
        else:
            html_commands.append(report_message(
                'Select two or more items to create a group.'))
        html_commands.append(invalidate(send=False))
    elif action == 'suppressFeatures':
        suppress = data.get('suppress', True)
        failures = 0
        for node in nodes_for(data):
            try:
                node.obj.isSuppressed = suppress
            except (RuntimeError, AttributeError):
                failures += 1
        if failures:
            verb = 'suppress' if suppress else 'unsuppress'
            html_commands.append(report_message(
                f'Could not {verb} {failures} of the selected items.'))
        html_commands.append(invalidate(send=False))
    elif action == 'deleteFeatures':
        nodes = list(nodes_for(data))

        # Delete later items first, so deleting one does not invalidate the
        # timeline positions of the others.
        def _node_index(n):
            try:
                return n.obj.index
            except (RuntimeError, AttributeError):
                return -1
        nodes.sort(key=_node_index, reverse=True)

        failures = 0
        for node in nodes:
            obj = node.obj
            deleted = False
            try:
                if obj.isGroup:
                    deleted = obj.deleteMe(False)
                else:
                    deleted = _delete_timeline_obj(obj)
            except (RuntimeError, AttributeError):
                deleted = False
            if not deleted:
                failures += 1
        if failures:
            html_commands.append(report_message(
                f'Could not delete {failures} of the selected items '
                '(they may be needed by later features).'))
        html_commands.append(invalidate(send=False))

    if html_commands:
        htmlArgs.returnData = json.dumps(html_commands)

# Set True to log every terminated command (id / reason / resourceFolder) to
# ~/vt_cmd_trace.log. Use it to confirm which command ids a machine fires during
# camera navigation, then extend NAV_COMMAND_IDS if the /camera/ skip missed one.
TRACE_COMMANDS = False  # dev-only: flip True to capture command ids to ~/vt_cmd_trace.log

def _is_navigation_command(eventArgs):
    # Build-independent nav skip: camera commands (orbit/pan/zoom/fit/look-at)
    # live under the Neutron .../Resources/Camera/ tree regardless of their id,
    # which varies by build (issue #9 — the id list alone missed Windows nav
    # commands). resourceFolder is read the same way trace_feature_image() does,
    # so this API is known-good; empty/None -> not treated as navigation.
    try:
        folder = eventArgs.commandDefinition.resourceFolder or ''
    except Exception:
        return False
    return '/camera/' in folder.lower()

def command_terminated_handler(args):
    eventArgs = adsk.core.ApplicationCommandEventArgs.cast(args)

    # As long as we don't update on command create, we only need to listen for command completion
    # Except Undo, which has a "Cancel" termination reason.
    if (eventArgs.terminationReason != adsk.core.CommandTerminationReason.CompletedTerminationReason and
        eventArgs.commandId != 'UndoCommand'):
        return

    if TRACE_COMMANDS:
        try:
            with open(os.path.expanduser('~/vt_cmd_trace.log'), 'a') as f:
                folder = eventArgs.commandDefinition.resourceFolder or ''
                f.write(f'{eventArgs.commandId}\t{eventArgs.terminationReason}\t{folder}\n')
        except Exception:
            pass

    # Commands that never change the timeline. Camera navigation MUST be skipped
    # here: on macOS/Windows it fires commandTerminated on every orbit/pan release
    # (it fires nothing on some builds — why the freeze only hit certain machines,
    # issue #9), and a full timeline rebuild costs ~10s on a 600-node design. The
    # debounce can't save it — the rebuild itself is the freeze, so we never start
    # it. The id set is a cheap fast-path; _is_navigation_command catches nav
    # commands whose id varies by build (the Windows stutter).
    if eventArgs.commandId in SKIP_REFRESH_COMMAND_IDS or _is_navigation_command(eventArgs):
        return

    schedule_refresh()

def trace_feature_image(command_terminated_event_args):
    ''' Development function to trace feature images '''
    _, timeline = thomasa88lib.timeline.get_timeline()
    feature = None
    if timeline:
        try:
            feature = thomasa88lib.utils.short_class(timeline.item(timeline.count-1).entity)
        except Exception as e:
            feature = str(e)
    folder = command_terminated_event_args.commandDefinition.resourceFolder
    if folder:
        folder = folder.replace(thomasa88lib.utils.get_fusion_deploy_folder() + '/', '')
    print(f"'{feature}': ('{folder}', ''),")

#########################################################################################
# app.product is not ready at workspaceActivated, but documentActivated does not fire
# when switching to/from Drawing. However, in that case, it seems that the product is
# ready when we call thomasa88lib.timeline.get_timeline (presumably since the panel has to be recreated)
# Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/api-bug-application-documentactivated-event-do-not-raise/m-p/9020750
#
# PLM360OpenAttachmentCommand + MarkDocumentsForOpenCommand could possibly be used as
# another workaround.
#
# Event order:
# DocumentActivating
# OnWorkspaceActivated
# DocumentActivated
# PLM360OpenAttachmentCommand or MarkDocumentsForOpenCommand
#

def workspace_pre_deactivate_handler(args):
    #eventArgs = adsk.core.DocumentEventArgs.cast(args)
    if not palette_closed_by_user:
        invalidate(clear=True)

def workspace_activated_handler(args):
    #eventArgs = adsk.core.WorkspaceEventArgs.cast(args)

    if get_active_workspace_id() == 'FusionSolidEnvironment':
        if not palette_closed_by_user:
            show_palette()
    else:
        # Deactivate
        hide_palette()

def document_activated_handler(args):
    #eventArgs = adsk.core.DocumentEventArgs.cast(args)
    if get_active_workspace_id() == 'FusionSolidEnvironment':
        if not palette_closed_by_user:
            show_palette()

def find_node_id_for_entity(native, token):
    '''Fallback entity->node match when the prebuilt token index misses.

    Scans the timeline cache comparing each node's live entity to the selected
    one (object identity first, then a freshly-read token), so both tokens come
    from the same moment. O(nodes), only hit on an index miss.'''
    if not timeline_cache_map:
        return None
    for node in timeline_cache_map.values():
        obj = node.obj
        if obj is None or node.children:
            # Top placeholder / group node: no selectable entity.
            continue
        try:
            entity = obj.entity
        except Exception:
            continue
        if entity is None:
            continue
        node_native = native_of(entity)
        if node_native == native:
            return node.id
        try:
            if node_native.entityToken == token:
                return node.id
        except Exception:
            pass
    return None

# Set True to log every GUI selection (entity class / which lookup matched) to
# ~/vt_selection_trace.log. Use it to see what Fusion actually delivers for a
# viewport click (issue #14): geometry clicks select a BRepFace/BRepEdge, which
# the public API cannot map back to the feature that created it.
TRACE_SELECTION = False

def active_selection_changed_handler(args):
    '''Highlight the timeline row(s) matching the feature selected in Fusion's GUI.

    Best-effort, O(selected): each selected entity is matched via the token
    index built at refresh time, then via its TimelineObject.index (tokens are
    documented as non-stable strings, the timeline position is not), and only
    then via the capped per-node scan. Anything that fails is swallowed so the
    user's selection flow is never disturbed.'''
    if not HIGHLIGHT_GUI_SELECTION:
        return

    palette = ui.palettes.itemById('thomasa88_verticalTimelinePalette')
    if not palette or not palette.isVisible or not html_ready or not timeline_cache_map:
        return

    selected_ids = []
    try:
        eventArgs = adsk.core.ActiveSelectionEventArgs.cast(args)
        for selection in eventArgs.currentSelection:
            entity = selection.entity
            if entity is None:
                continue
            native = native_of(entity)
            node_id = None
            token = None
            matched_by = 'none'
            try:
                token = native.entityToken
                node_id = timeline_cache_entity_index.get(token)
                matched_by = 'token'
            except Exception:
                pass
            if node_id is None:
                # Timeline entities (features, sketches, planes, occurrences)
                # expose their TimelineObject; its index is an O(1) key into the
                # position map at any design size. BRep geometry has no
                # timelineObject and skips through. index is -1 inside a
                # collapsed group — never in the map, so it misses cleanly.
                try:
                    node_id = timeline_cache_position_index.get(
                        native.timelineObject.index)
                    matched_by = 'position'
                except Exception:
                    pass
            if node_id is None and len(timeline_cache_map) <= FALLBACK_SCAN_MAX_NODES:
                # Last resort: compare the selected entity against each node's
                # live entity, both read in this same moment. Capped: the
                # per-node obj.entity scan freezes large assemblies (issue #9).
                node_id = find_node_id_for_entity(native, token)
                matched_by = 'scan'
            if node_id is None:
                matched_by = 'none'
            if TRACE_SELECTION:
                try:
                    with open(os.path.expanduser('~/vt_selection_trace.log'), 'a') as f:
                        f.write(f'{entity.classType()}\t{matched_by}\t{node_id}\n')
                except Exception:
                    pass
            if node_id is not None:
                selected_ids.append(node_id)
    except Exception:
        # Highlighting is purely cosmetic and must never raise.
        return

    palette.sendInfoToHTML('highlightFeatures', json.dumps({'ids': selected_ids}))

#########################################################################################