# This file is part of VerticalTimeline, a Fusion 360 add-in that
# provides a vertical timeline.
#
# Copyright (C) 2020  Thomas Axelsson
#
# This work is dual-licensed under GPL 3.0 (or any later version) and MIT.
# You can choose between one of them if you use this work.

# Icon / resource resolution for the timeline rows and the right-click menu.
# Split out of VerticalTimeline.py: this is the most-churned area (Fusion ships
# its icons under a tangle of Fusion-vs-Neutron trees with a macOS/Windows path
# split and theme-split filenames) and it has almost no coupling to the rest of
# the add-in. See docs/ICONS.md for the on-disk layout.
#
# Self-contained: reads the active UI via the adsk Application singleton (only
# find_command_def_by_name needs it) rather than a global injected from main.

import os
import adsk.core
from .thomasa88lib import utils, timeline

FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# Occurrence types
OCCURRENCE_UNKNOWN_COMP = 0
OCCURRENCE_NEW_COMP = 1
OCCURRENCE_COPY_COMP = 2
OCCURRENCE_SHEET_METAL = 3
OCCURRENCE_BODIES_COMP = 4
OCCURRENCE_CUT_COMP = 5
OCCURRENCE_PIN_COMP = 6

# Occurrence types whose timeline name is a fixed read-only prefix + the
# component's instance name (not a bare, renameable component name). The row's
# name isn't offered as a component rename for these. (CopyPaste is historically
# left out of this set - existing behavior.)
OCCURRENCE_PREFIXED_TYPES = (OCCURRENCE_BODIES_COMP, OCCURRENCE_CUT_COMP,
                             OCCURRENCE_PIN_COMP)

OCCURRENCE_RESOURCE_MAP = {
    OCCURRENCE_NEW_COMP: ('Fusion/UI/FusionUI/Resources/Modeling/BooleanNewComponent', ''),
    OCCURRENCE_COPY_COMP: ('Fusion/UI/FusionUI/Resources/Assembly/CopyPasteInstance', ''),
    # Neutron browser icon, renamed from the old ComponentSheetMetal. Its path
    # relative to the deploy folder differs between macOS and Windows, so list
    # both layouts (first that exists wins).
    OCCURRENCE_SHEET_METAL: ([
        '../../Neutron/Neutron/UI/Base/Resources/Browser/SheetMetalComponent',  # macOS bundle
        'Neutron/UI/Base/Resources/Browser/SheetMetalComponent',                # Windows webdeploy
    ], ''),
    # "Create components from bodies" - Fusion's own timeline shows the
    # CreateComponentFromBody glyph (box -> component) for these rows.
    OCCURRENCE_BODIES_COMP: ('Fusion/UI/FusionUI/Resources/Assembly/CreateComponentFromBody', ''),
    # Cut-paste and pinned occurrences each get their matching Fusion icon
    # instead of falling through to the generic component glyph.
    OCCURRENCE_CUT_COMP: ('Fusion/UI/FusionUI/Resources/Assembly/CutPasteInstance', ''),
    OCCURRENCE_PIN_COMP: ('Fusion/UI/FusionUI/Resources/Assembly/PinOccurrence', ''),
    OCCURRENCE_UNKNOWN_COMP: ('Fusion/UI/FusionUI/Resources/finish/finishX', '')
}

PLANE_RESOURCE_MAP = {
    # Edit command ids verified against a live Fusion session's
    # ui.commandDefinitions (#15) - the previous ids were guessed and didn't
    # exist, so itemById() returned None and crashed on .execute(). Tangent and
    # TangentAtPoint share one command: Fusion merged those two creation flows
    # into a single "Tangent Plane" dialog.
    'ConstructionPlaneOffsetDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_offset', 'FusionDcEditConstructionPlaneByPlaneOffsetCommand'),
    'ConstructionPlaneAtAngleDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_angle', 'FusionDcEditConstructionPlaneAtAngleCommand'),
    'ConstructionPlaneTangentDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_tangent', 'FusionDcEditConstructionTangentPlaneCommand'),
    'ConstructionPlaneMidplaneDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_midplane', 'FusionDcEditConstructionMidPlaneCommand'),
    'ConstructionPlaneTwoEdgesDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_two_axis', 'FusionDcEditConstructionPlaneFromTwoEdgesCommand'),
    'ConstructionPlaneThreePointsDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_three_points', 'FusionDcEditConstructionPlaneFromThreePointsCommand'),
    'ConstructionPlaneTangentAtPointDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_point_face', 'FusionDcEditConstructionTangentPlaneCommand'),
    'ConstructionPlaneDistanceOnPathDefinition': ('Fusion/UI/FusionUI/Resources/construction/plane_onpath', 'FusionDcEditConstructionPlaneAlongPathCommand'),
}

# Generic construction-plane glyph used when we can't tell which kind of plane it
# is: the definition type isn't in the map above, or Fusion blocks access to
# .definition entirely (raises InternalValidationError on some planes, #8). Beats
# falling through to the "info access prohibited" placeholder.
PLANE_FALLBACK_RES = ('Fusion/UI/FusionUI/Resources/tools/SymbolPalette/Plane', '')
def get_plane_res(i):
    try:
        match = PLANE_RESOURCE_MAP.get(utils.short_class(i.entity.definition))
    except Exception:
        match = None
    return match or PLANE_FALLBACK_RES

# Same per-definition pattern as PLANE_RESOURCE_MAP, ids verified live (#8-family
# follow-up). NormalToFaceAtPoint and PerpendicularAtPoint share one edit command:
# Fusion merged those two creation flows into a single "Perpendicular to Face" dialog.
AXIS_RESOURCE_MAP = {
    'ConstructionAxisCircularFaceDefinition': ('Fusion/UI/FusionUI/Resources/construction/axis_line', 'FusionDcEditConstructionAxisThroughCylinderCommand'),
    'ConstructionAxisEdgeDefinition': ('Fusion/UI/FusionUI/Resources/construction/axis_line', 'FusionDcEditConstructionAxisThroughEdgeCommand'),
    'ConstructionAxisNormalToFaceAtPointDefinition': ('Fusion/UI/FusionUI/Resources/construction/axis_line', 'FusionDcEditConstructionAxisNormalToFaceCommand'),
    'ConstructionAxisPerpendicularAtPointDefinition': ('Fusion/UI/FusionUI/Resources/construction/axis_line', 'FusionDcEditConstructionAxisNormalToFaceCommand'),
    'ConstructionAxisTwoPlaneDefinition': ('Fusion/UI/FusionUI/Resources/construction/axis_line', 'FusionDcEditConstructionAxisFromTwoPlanesCommand'),
    'ConstructionAxisTwoPointDefinition': ('Fusion/UI/FusionUI/Resources/construction/axis_line', 'FusionDcEditConstructionAxisThroughTwoPointsCommand'),
    # ConstructionAxisByLineDefinition (non-parametric direct-edit axes) has no
    # dedicated edit command, so it's intentionally absent - falls to the fallback below.
}
AXIS_FALLBACK_RES = ('Fusion/UI/FusionUI/Resources/construction/axis_line', '')
def get_axis_res(i):
    try:
        match = AXIS_RESOURCE_MAP.get(utils.short_class(i.entity.definition))
    except Exception:
        match = None
    return match or AXIS_FALLBACK_RES

POINT_RESOURCE_MAP = {
    'ConstructionPointCenterDefinition': ('Fusion/UI/FusionUI/Resources/construction/point_center', 'FusionDcEditConstructionPointFromCircleOrSphereCommand'),
    'ConstructionPointDistanceOnPathDefinition': ('Fusion/UI/FusionUI/Resources/construction/point_center', 'FusionDcEditConstructionPointAlongPathCommand'),
    'ConstructionPointEdgePlaneDefinition': ('Fusion/UI/FusionUI/Resources/construction/point_center', 'FusionDcEditConstructionPointAtEdgeAndPlaneCommand'),
    'ConstructionPointPointDefinition': ('Fusion/UI/FusionUI/Resources/construction/point_center', 'FusionDcEditConstructionPointFromPointCommand'),
    'ConstructionPointThreePlanesDefinition': ('Fusion/UI/FusionUI/Resources/construction/point_center', 'FusionDcEditConstructionPointFromThreePlanesCommand'),
    'ConstructionPointTwoEdgesDefinition': ('Fusion/UI/FusionUI/Resources/construction/point_center', 'FusionDcEditConstructionPointThroughTwoEdgesCommand'),
}
POINT_FALLBACK_RES = ('Fusion/UI/FusionUI/Resources/construction/point_center', '')
def get_point_res(i):
    try:
        match = POINT_RESOURCE_MAP.get(utils.short_class(i.entity.definition))
    except Exception:
        match = None
    return match or POINT_FALLBACK_RES

# Mesh-editing icons live in the ParaMesh library — a sibling of the Fusion
# tree, like Neutron, with the same macOS/Windows path split (docs/ICONS.md).
def _paramesh(name):
    return ([f'../ParaMesh/UI/ParaMeshUI/Resources/Icons/{name}',  # macOS bundle
             f'ParaMesh/UI/ParaMeshUI/Resources/Icons/{name}'],    # Windows webdeploy
            '')

FEATURE_RESOURCE_MAP = {
    # This list is hand-crafted. Please respect the work put into this list and
    # retain the Copyright and License stanzas if you copy it.
    # Helpful tools: trace_feature_image function, ImageSorter, Process Monitor.
    # Resources are found in %localappdata%\Autodesk\webdeploy\production\*\
    'Sketch': ('Fusion/UI/FusionUI/Resources/sketch/Sketch_feature', 'SketchActivate'),
    'FormFeature': ('Fusion/UI/FusionUI/Resources/TSpline/TSplineBaseFeatureCreation', 'TSplineBaseFeatureActivate'),
    'LoftFeature': lambda i: ('Fusion/UI/FusionUI/Resources/solid/loft', 'FusionLoftEditCommand') if i.entity.isSolid else ('Fusion/UI/FusionUI/Resources/surface/loft', 'FusionSurfaceLoftEditCommand'),
    'ExtrudeFeature': lambda i: ('Fusion/UI/FusionUI/Resources/solid/extrude', 'FusionExtrudeEditCommand') if i.entity.isSolid else ('Fusion/UI/FusionUI/Resources/surface/extrude', 'FusionSurfaceExtrudeEditCommand'),
    'Occurrence': lambda i: OCCURRENCE_RESOURCE_MAP[timeline.get_occurrence_type(i)],
    'BoundaryFillFeature': ('Fusion/UI/FusionUI/Resources/surface/surface_sculpt', 'FusionSculptEditCommand'),
    'SurfaceDeleteFaceFeature': ('Fusion/UI/FusionUI/Resources/modify/surface_delete', 'FusionDcSurfaceDeleteFaceEditCommand'),
    'RevolveFeature': lambda i: ('Fusion/UI/FusionUI/Resources/solid/revolve', 'FusionRevolveEditCommand') if i.entity.isSolid else ('Fusion/UI/FusionUI/Resources/surface/revolve', 'FusionSurfaceRevolveEditCommand'),
    'SweepFeature': lambda i: ('Fusion/UI/FusionUI/Resources/solid/sweep', 'FusionSweepEditCommand') if i.entity.isSolid else ('Fusion/UI/FusionUI/Resources/surface/sweep', 'FusionSurfaceSweepEditCommand'),
    'RibFeature': ('Fusion/UI/FusionUI/Resources/solid/rib', 'FusionDcRibEditCommand'),
    'WebFeature': ('Fusion/UI/FusionUI/Resources/solid/web', 'FusionDcWebEditCommand'),
    'Thomasa88Feature': ('Vertical/Timeline', 'FeatureMap'),
    'BoxFeature': ('Fusion/UI/FusionUI/Resources/solid/primitive_box', 'BoxPrimitiveEditCommand'),
    'CylinderFeature': ('Fusion/UI/FusionUI/Resources/solid/primitive_cylinder', 'CylinderPrimitiveEditCommand'),
    'SphereFeature': ('Fusion/UI/FusionUI/Resources/solid/primitive_sphere', 'SpherePrimitiveEditCommand'),
    'TorusFeature': ('Fusion/UI/FusionUI/Resources/solid/primitive_torus', 'TorusPrimitiveEditCommand'),
    'CoilFeature': ('Fusion/UI/FusionUI/Resources/solid/Coil', 'CoilPrimitiveEditCommand'),
    'PipeFeature': ('Fusion/UI/FusionUI/Resources/solid/primitive_pipe', 'PipePrimitiveEditCommand'),
    'RectangularPatternFeature': ('Fusion/UI/FusionUI/Resources/pattern/pattern_rectangular', 'FusionDcRectangularPatternEditCommand'),
    'CircularPatternFeature': ('Fusion/UI/FusionUI/Resources/pattern/pattern_circular', 'FusionDcCircularPatternEditCommand'),
    'PathPatternFeature': ('Fusion/UI/FusionUI/Resources/pattern/pattern_path', 'FusionDcPathPatternEditCommand'),
    'MirrorFeature': ('Fusion/UI/FusionUI/Resources/pattern/pattern_mirror', 'FusionDcMirrorPatternEditCommand'),
    'ThickenFeature': ('Fusion/UI/FusionUI/Resources/surface/thicken', 'FusionDcSurfaceThickenEditCommand'),
    'BaseFeature': ('Fusion/UI/FusionUI/Resources/Modeling/BaseFeature', 'BaseFeatureActivate'),
    'RemoveFeature': ('Fusion/UI/FusionUI/Resources/_return', ''),
    'HoleFeature': ('Fusion/UI/FusionUI/Resources/solid/hole', 'FusionDcHoleEditCommand'),
    'ThreadFeature': ('Fusion/UI/FusionUI/Resources/solid/thread', 'FusionDcThreadEditCommand'),

    # Solid Modify
    'FilletFeature': ('Fusion/UI/FusionUI/Resources/Modeling/FilletEdges', 'FusionDcFilletEditCommand'),
    'ChamferFeature': ('Fusion/UI/FusionUI/Resources/Modeling/Chamfer', 'FusionDcChamferEditCommand'),
    'ShellFeature': ('Fusion/UI/FusionUI/Resources/Modeling/ShellBody', 'FusionDcShellFeatureEditCommand'),
    'DraftFeature': ('Fusion/UI/FusionUI/Resources/solid/draft', 'FusionDcDraftEditCommand'),
    'ScaleFeature': ('Fusion/UI/FusionUI/Resources/modify/scale', 'FusionDcScaleEditCommand'),
    'CombineFeature': ('Fusion/UI/FusionUI/Resources/modify/combine', 'FusionCombineEditCommand'),
    'ReplaceFaceFeature': ('Fusion/UI/FusionUI/Resources/modify/replace_face', 'FusionDcReplaceFaceEditCommand'),
    'SplitFaceFeature': ('Fusion/UI/FusionUI/Resources/modify/split_face', 'FusionDcSplitFaceEditCommand'),
    'SplitBodyFeature': ('Fusion/UI/FusionUI/Resources/modify/split', 'FusionDcSplitBodyEditCommand'),

    # Surface Create only
    'OffsetFacesFeature': ('Fusion/UI/FusionUI/Resources/Modeling/OffsetFaces', 'FusionOffsetFacesEditCommand'),
    'PatchFeature': ('Fusion/UI/FusionUI/Resources/surface/patch', 'FusionSurfacePatchEditCommand'),
    'RuledSurfaceFeature': ('Fusion/UI/FusionUI/Resources/surface/ruled', 'FusionDcSurfaceRuledEditCommand'),
    'OffsetFeature': ('Fusion/UI/FusionUI/Resources/surface/offset', 'FusionDcSurfaceOffsetEditCommand'),

    # Surface Modify only
    'TrimFeature': ('Fusion/UI/FusionUI/Resources/surface/trim', 'FusionDcSurfaceTrimEditCommand'),
    'ExtendFeature': ('Fusion/UI/FusionUI/Resources/surface/extend', 'FusionDcSurfaceExtendEditCommand'),
    'StitchFeature': ('Fusion/UI/FusionUI/Resources/surface/stitch', 'FusionSurfaceStitchEditCommand'),
    'UnstitchFeature': ('Fusion/UI/FusionUI/Resources/surface/unstitch', 'FusionSurfaceUnStitchEditCommand'),
    'ReverseNormalFeature': ('Fusion/UI/FusionUI/Resources/modify/surface_reverse_normal', 'FusionDcReverseNormalEdit'),

    # Assembly
    'Joint': ('Fusion/UI/FusionUI/Resources/Assembly/joint', 'DcEditJointAssembleCmd'),
    'AsBuiltJoint': ('Fusion/UI/FusionUI/Resources/Assembly/JointAsBuilt', 'DcEditJointAsBuiltCmd'),
    'JointOrigin': ('Fusion/UI/FusionUI/Resources/construction/jointorigin', 'EditJointOriginR2Cmd'),
    'RigidGroup': ('Fusion/UI/FusionUI/Resources/Assembly/RigidGroup', 'DcEditRigidGroupCmd'),
    'Snapshot': ('Fusion/UI/FusionUI/Resources/Assembly/Snapshot', 'SnapshotActivate'),

    # Planes
    'ConstructionPlane': get_plane_res,

    # Move/Align. Historically Fusion did not allow accessing the entity of these
    # features (see bug link below), so they fell back to the "info access
    # prohibited" placeholder. Newer Fusion versions expose the entity; map them
    # so they get a proper icon and become editable. If the entity is still
    # inaccessible, get_features_from_node() handles the RuntimeError gracefully
    # and these entries are simply never reached.
    # NOTE: the icons live under modify/ and Assembly/, NOT Modeling/ - the
    # earlier Modeling/Move + Modeling/Align paths don't exist on disk, so these
    # rows fell through to the finishX placeholder even when editable (#8).
    'MoveFeature': ('Fusion/UI/FusionUI/Resources/modify/move', 'FusionDcMoveCopyEditCommand'),
    'AlignFeature': ('Fusion/UI/FusionUI/Resources/Assembly/Align', 'FusionDcAlignEditCommand'),

    # Mesh, attached canvas ("frame"-like image), and copy/paste-body features -
    # surface in the timeline but weren't mapped, so they showed the finishX
    # placeholder (#8). Icon only; add edit-command ids if double-click-to-edit
    # is wanted later. # ponytail: icon only, no edit wiring yet.
    'MeshFeature': ('Fusion/UI/FusionUI/Resources/Mesh/MeshBody', ''),
    'MeshConvertFeature': ('Fusion/UI/FusionUI/Resources/Mesh/Convert', ''),
    # Mesh-editing features (#13). Icon only, no edit wiring yet.
    'MeshRepairFeature': _paramesh('ParaMeshRepair'),
    'MeshRemeshFeature': _paramesh('ParaMeshRemesh'),
    'MeshReduceFeature': _paramesh('ParaMeshReduce'),
    'MeshGenerateFaceGroupsFeature': _paramesh('ParaMeshCalculateFaceGroups'),
    'MeshCombineFaceGroupsFeature': _paramesh('ParaMeshMergeFaceGroups'),
    'MeshCombineFeature': _paramesh('ParaMeshCombine'),
    'MeshRemoveFeature': _paramesh('ParaMeshRemove'),
    'MeshReverseNormalFeature': _paramesh('ParaMeshReverseNormals'),
    'MeshSeparateFeature': _paramesh('ParaMeshSeparate'),
    'MeshShellFeature': _paramesh('ParaMeshHollow'),
    'MeshSmoothFeature': _paramesh('ParaMeshSmooth'),
    'Canvas': ('Fusion/UI/FusionUI/Resources/Image/AddCanvas', ''),
    'CopyPasteBody': ('Fusion/UI/FusionUI/Resources/Assembly/CopyPasteBodies', ''),

    # More features that surface in the timeline but weren't mapped, so they
    # showed the finishX placeholder. Icons verified on disk; edit command ids
    # verified live against a running Fusion session's ui.commandDefinitions.
    'EmbossFeature': ('Fusion/UI/FusionUI/Resources/Modeling/Emboss', 'FusionDcEmbossEditCmd'),
    # RuleFilletFeature: distinct from FilletFeature ('FusionDcFilletEditCommand',
    # tooltip-confirmed) and sheet-metal fillet ('FusionSheetMetalFilletEditCommand',
    # tooltip-confirmed). This is the one remaining "Edit Feature"-labeled fillet
    # command with no tooltip authored - best match by elimination, not tooltip-verified.
    'RuleFilletFeature': ('Fusion/UI/FusionUI/Resources/solid/rulefillet', 'FusionDcFilletFeatureEditCommand'),
    'DeleteFaceFeature': ('Fusion/UI/FusionUI/Resources/Modeling/DeleteFaces', 'FusionDcDeleteFaceEditCommand'),  # solid delete-face, vs SurfaceDeleteFaceFeature
    'DeriveFeature': ('Fusion/UI/FusionUI/Resources/Derive/CloneWM', 'EditDeriveCommand'),  # insert-derive (see comment block below)
    # Construction axis/point: per-definition map + edit ids, same pattern as
    # PLANE_RESOURCE_MAP above.
    'ConstructionAxis': get_axis_res,
    'ConstructionPoint': get_point_res,

    # Bug: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/api-bug-cannot-access-entity-of-quot-move-quot-feature/m-p/9651921
    # '2 : InternalValidationError : res': 'Fusion/UI/FusionSheetMetalUI/Resources/Flange',
    # '2 : InternalValidationError : res': 'Fusion/UI/FusionSheetMetalUI/Resources/Bend',
    # '2 : InternalValidationError : res': 'Fusion/UI/FusionSheetMetalUI/Resources/ConvertToSheetMetal',
    # '2 : InternalValidationError : res': 'Fusion/UI/FusionSheetMetalUI/Resources/FlatPattern',
    # insert derive feature: 'Fusion/UI/FusionUI/Resources/Derive/CloneWM',
}

UNKNOWN_FEATURE_IMAGE = 'Fusion/UI/FusionUI/Resources/finish/finishX'

# Fusion's "fully constrained sketch" browser icon (the sketch glyph with a lock
# badge). It lives in the Neutron library, whose location relative to the deploy
# folder differs between the macOS app bundle and the Windows webdeploy, so try
# both. Resolves to None (-> plain sketch icon) if neither layout matches.
# See docs/ICONS.md for the macOS/Windows Neutron path split.
# ponytail: two known layouts; add another candidate if a future layout misses.
SKETCH_FULLY_CONSTRAINED_RES = [
    '../../Neutron/Neutron/UI/Base/Resources/Browser/FullyConstrainedSketch',  # macOS bundle
    'Neutron/UI/Base/Resources/Browser/FullyConstrainedSketch',                # Windows webdeploy
]

def get_first_image_path(subpaths, dark=False):
    '''First of several candidate resource subpaths that exists, or None.'''
    for sub in subpaths:
        path = get_image_path(sub, dark)
        if path:
            return path
    return None

# Feature types already reported as unresolved (finishX fallback), so the
# Text Commands console gets one line per type per session, not one per row
# per refresh. Makes every finishX sighting self-identifying (#8/#12/#13).
_no_icon_reported = set()

def get_feature_image(obj, entity=None, fusion_type=None):
    '''(light, dark) icon paths so the palette can match its current theme.'''
    match = get_feature_res(obj, entity, fusion_type)

    def resolve(dark):
        image = None
        if match and match[0]:
            # match[0] is usually a single resource subpath, but may be a list of
            # candidates when the resource lives in a library whose layout differs
            # between platforms (e.g. the Neutron browser icons).
            if isinstance(match[0], (list, tuple)):
                image = get_first_image_path(match[0], dark)
            else:
                image = get_image_path(match[0], dark)
        if not image:
            # Image not mapped, or the mapped resource does not exist in this
            # Fusion version. Fall back to a generic placeholder.
            image = get_image_path(UNKNOWN_FEATURE_IMAGE, dark)
            key = fusion_type or '?'
            if key not in _no_icon_reported:
                _no_icon_reported.add(key)
                print(f"Vertical Timeline: no icon resolved for feature type "
                      f"'{key}' (mapped: {match is not None})")
        return image

    return resolve(False), resolve(True)

def set_feature_image(feature, subpath_or_list):
    '''Set feature['image'] (light) and ['imageDark'] from a resource subpath or
    candidate list, so the palette can pick the one matching its theme.'''
    if isinstance(subpath_or_list, (list, tuple)):
        feature['image'] = get_first_image_path(subpath_or_list, False)
        feature['imageDark'] = get_first_image_path(subpath_or_list, True)
    else:
        feature['image'] = get_image_path(subpath_or_list, False)
        feature['imageDark'] = get_image_path(subpath_or_list, True)

def get_feature_edit_command_id(obj):
    match = get_feature_res(obj)

    if not match or not match[1]:
        return None
    else:
        return match[1]

def get_feature_res(obj, entity=None, fusion_type=None):
    # entity / fusion_type are passed in on the hot refresh path so we don't
    # re-fetch obj.entity (an API round-trip) and recompute short_class for
    # every feature; default to reading them for the occasional direct caller.
    if entity is None:
        entity = obj.entity
    if fusion_type is None:
        fusion_type = utils.short_class(entity)
    match = FEATURE_RESOURCE_MAP.get(fusion_type)
    if callable(match):
        try:
            match = match(obj)
        except Exception:
            # Resolving the icon for some features digs deeper into the entity
            # (e.g. ConstructionPlane reads .entity.definition). That can be
            # None or inaccessible for default/origin planes and while a
            # document is being torn down on close. Fall back to the
            # placeholder icon instead of crashing the whole palette refresh.
            match = None
    return match

# How Fusion lays out its icon resources (deploy folder, the Fusion vs Neutron
# trees, the macOS app-bundle vs Windows webdeploy split, and theme-split
# filenames like 16x16-dark.png) is documented in docs/ICONS.md.
#
# Resolved icon paths are cached: the Fusion deploy folder and the bundled
# resource files do not change during a session, so there is no need to hit the
# filesystem (os.path.exists) once per feature on every timeline refresh.
_image_path_cache = {}
# Icons render in a 16px box but on Retina that needs a 32px source or it looks
# soft, so prefer the 2x raster (16x16@2x.png, or 32x32.png where a folder names
# it that way), falling back to the plain 16px PNG, then SVG. Fusion ships
# theme-split assets: the neutral files have a dark foreground (right on a light
# palette) and the "-dark" files a light foreground (right on a dark palette).
# The dark set falls back to the neutral set for the many icons with no "-dark".
_ICON_NEUTRAL_NAMES = ('16x16@2x.png', '32x32.png', '16x16.png', '16x16.svg',
                       '16x16-dark.svg')
def _icon_in_folder(folder, dark=False):
    '''First icon file that exists in an already-resolved folder. Shared by
    subpath lookups (get_image_path) and native-command icons taken from a
    command's absolute resourceFolder.'''
    if dark:
        names = ('16x16-dark@2x.png', '32x32-dark.png', '16x16-dark.png',
                 '16x16-dark.svg') + _ICON_NEUTRAL_NAMES
    else:
        names = _ICON_NEUTRAL_NAMES
    for name in names:
        path = f'{folder}/{name}'
        if os.path.exists(path):
            return path
    return None

def get_image_path(subpath, dark=False):
    key = (subpath, dark)
    if key in _image_path_cache:
        return _image_path_cache[key]

    base = f'{utils.get_fusion_deploy_folder()}/{subpath}'
    result = _icon_in_folder(base, dark)
    if result is None:
        print(f'File does not exist: {base}/{_ICON_NEUTRAL_NAMES[0]}')

    _image_path_cache[key] = result
    return result

def find_command_def_by_name(name):
    '''Look up one of Fusion's command definitions by its display name (the
    label shown in the native menu). Matching by label - not a hard-coded id -
    keeps these working without guessing internal command ids. Returns None if
    Fusion doesn't expose a command with that name.'''
    target = name.strip().rstrip('.').lower()
    defs = adsk.core.Application.get().userInterface.commandDefinitions
    prefix_match = None
    for i in range(defs.count):
        d = defs.item(i)
        try:
            n = (d.name or '').strip().rstrip('.').lower()
        except Exception:
            continue
        if n == target:
            return d
        if prefix_match is None and target and n.startswith(target):
            prefix_match = d
    return prefix_match

def get_command_icon_pair(name):
    '''Light/dark menu icon for one of Fusion's own commands, read from its
    command definition's resourceFolder so the menu shows the exact native icon.
    None if the command or its icon can't be found.'''
    # ponytail: only used for commands that ship no stable resource subpath of
    # their own. Resolves once at menu-build time; if the name doesn't resolve the
    # item is simply icon-less - the same graceful path the action itself takes.
    cmd = find_command_def_by_name(name)
    try:
        folder = cmd.resourceFolder if cmd else None
    except Exception:
        folder = None
    if not folder:
        return None
    light = _icon_in_folder(folder, False)
    if not light:
        return None
    return {'light': light, 'dark': _icon_in_folder(folder, True) or light}

# Icons for the palette right-click menu, taken from Fusion's own command
# resources so the menu matches the native look. Resolved once and cached; any
# command/icon that cannot be found is simply omitted (no icon shown for it).
# The 'Edit' item uses the feature's own icon and is handled in the palette.
_menu_icons_cache = None
def get_menu_icons():
    global _menu_icons_cache
    if _menu_icons_cache is not None:
        return _menu_icons_cache

    icons = {}

    # Each value is a {'light', 'dark'} pair (theme-split, like the row icons) so
    # the palette can pick the variant matching its current theme.
    def pair(subpath):
        light = get_image_path(subpath, False)
        if not light:
            return None
        return {'light': light, 'dark': get_image_path(subpath, True) or light}

    # Roll: the exact "Roll Timeline Marker Here" glyph (Fusion's FusionRollCommand)
    # is drawn by the timeline control and isn't shipped as a resource file, so we
    # bundle a transparent recreation of it. Fall back to Fusion's roll-forward
    # timeline icon if the bundled file is missing.
    roll_icon = os.path.join(FILE_DIR, 'resources', 'roll-marker.png')
    if os.path.exists(roll_icon):
        icons['rollToFeature'] = {'light': roll_icon, 'dark': roll_icon}
    else:
        roll_pair = pair('Fusion/UI/FusionUI/Resources/Timeline/RollFwd')
        if roll_pair:
            icons['rollToFeature'] = roll_pair

    # Delete: Fusion's own modify-panel red X. (Previously this borrowed the live
    # DeleteCommand's resourceFolder, which stopped resolving and left the menu
    # entry icon-less; this stable subpath ships a plain 16x16.png and resolves on
    # both macOS and Windows.) See docs/ICONS.md for the resource-tree layout.
    delete_pair = pair('Fusion/UI/FusionUI/Resources/modify/delete')
    if delete_pair:
        icons['deleteFeature'] = delete_pair

    # Create Group: Fusion's timeline group icon.
    group_pair = pair('Fusion/UI/FusionUI/Resources/Timeline/GroupFeature')
    if group_pair:
        icons['createGroup'] = group_pair

    # Suppress and Rename intentionally have no icon - this matches Fusion's
    # native timeline menu, and the only on-disk suppress icons are joint /
    # rigid-group specific (misleading for arbitrary features).

    # Show/Hide and the sketch display toggles (Profile / Dimension / Projected /
    # Construction geometry) all use Fusion's eye icon, matching the browser-tree
    # menu in the issue screenshots.
    eye_pair = pair('Fusion/UI/FusionUI/Resources/Timeline/Eye')
    if eye_pair:
        icons['toggleVisibility'] = eye_pair

    # Native sketch right-click options, with Fusion's own icons so the menu
    # matches the native look.
    lost_pair = pair('Fusion/UI/FusionUI/Resources/sketch/sketch_relinkProjection')
    if lost_pair:
        icons['manageLostProjections'] = lost_pair
    config_pair = pair('Fusion/UI/FusionUI/Resources/Modeling/DesignConfiguration')
    if config_pair:
        icons['configure'] = config_pair
    # Look At lives in the Neutron tree, whose path differs between the macOS app
    # bundle and the Windows webdeploy layout (same split as the browser icons).
    lookat_subs = ['../../Neutron/Neutron/UI/Commands/Resources/Camera/LookAt',
                   'Neutron/UI/Commands/Resources/Camera/LookAt']
    look_light = get_first_image_path(lookat_subs, False)
    if look_light:
        icons['lookAt'] = {'light': look_light,
                           'dark': get_first_image_path(lookat_subs, True) or look_light}
    # Redefine Sketch Plane ships no stable resource subpath, so take its icon
    # from the live command definition.
    redefine = get_command_icon_pair('Redefine Sketch Plane')
    if redefine:
        icons['redefineSketchPlane'] = redefine

    # Convert to DM Feature: ships no stable resource subpath, so take its icon
    # from the live command definition (the exact orange base-feature glyph).
    convert_pair = get_command_icon_pair('Convert to DM Feature')
    if convert_pair:
        icons['convertToDM'] = convert_pair
    # Review warning: the Neutron browser warning glyph (same tree/path split as
    # Look At and the browser row icons).
    warn_subs = ['../../Neutron/Neutron/UI/Base/Resources/Browser/WarningInSubItem',
                 'Neutron/UI/Base/Resources/Browser/WarningInSubItem']
    warn_light = get_first_image_path(warn_subs, False)
    if warn_light:
        icons['reviewWarning'] = {'light': warn_light,
                                  'dark': get_first_image_path(warn_subs, True) or warn_light}

    _menu_icons_cache = icons
    return icons
