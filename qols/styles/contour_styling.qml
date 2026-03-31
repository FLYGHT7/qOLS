<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis styleCategories="AllStyleCategories" labelsEnabled="1" version="3.44.0-Solothurn"
  hasScaleBasedVisibilityFlag="0" minScale="100000000" maxScale="0"
  simplifyDrawingHints="0" simplifyDrawingTol="1" simplifyLocal="1"
  simplifyAlgorithm="0" simplifyMaxScale="1" readOnly="0"
  symbologyReferenceScale="-1" autoRefreshTime="0" autoRefreshMode="Disabled">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <renderer-v2 type="singleSymbol" symbollevels="0" enableorderby="0"
    forceraster="0" referencescale="-1">
    <symbols>
      <symbol type="line" clip_to_extent="1" force_rhr="0" is_animated="0"
        frame_rate="10" alpha="1" name="0">
        <data_defined_properties>
          <Option type="Map">
            <Option type="QString" value="" name="name"/>
            <Option name="properties"/>
            <Option type="QString" value="collection" name="type"/>
          </Option>
        </data_defined_properties>
        <layer id="{contour-line-layer}" enabled="1" pass="0" locked="0" class="SimpleLine">
          <Option type="Map">
            <Option type="QString" value="0" name="align_dash_pattern"/>
            <Option type="QString" value="square" name="capstyle"/>
            <Option type="QString" value="5;2" name="customdash"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="customdash_map_unit_scale"/>
            <Option type="QString" value="MM" name="customdash_unit"/>
            <Option type="QString" value="0" name="dash_pattern_offset"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="dash_pattern_offset_map_unit_scale"/>
            <Option type="QString" value="MM" name="dash_pattern_offset_unit"/>
            <Option type="QString" value="0" name="draw_inside_polygon"/>
            <Option type="QString" value="bevel" name="joinstyle"/>
            <Option type="QString" value="255,1,1,255,rgb:1,0.0039216,0.0039216,1" name="line_color"/>
            <Option type="QString" value="solid" name="line_style"/>
            <Option type="QString" value="0.26" name="line_width"/>
            <Option type="QString" value="MM" name="line_width_unit"/>
            <Option type="QString" value="0" name="offset"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
            <Option type="QString" value="MM" name="offset_unit"/>
            <Option type="QString" value="0" name="ring_filter"/>
            <Option type="QString" value="0" name="trim_distance_end"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="trim_distance_end_map_unit_scale"/>
            <Option type="QString" value="MM" name="trim_distance_end_unit"/>
            <Option type="QString" value="0" name="trim_distance_start"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="trim_distance_start_map_unit_scale"/>
            <Option type="QString" value="MM" name="trim_distance_start_unit"/>
            <Option type="QString" value="0" name="tweak_dash_pattern_on_corners"/>
            <Option type="QString" value="0" name="use_custom_dash"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="width_map_unit_scale"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option type="QString" value="" name="name"/>
              <Option name="properties"/>
              <Option type="QString" value="collection" name="type"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </symbols>
    <rotation/>
    <sizescale/>
    <data-defined-properties>
      <Option type="Map">
        <Option type="QString" value="" name="name"/>
        <Option name="properties"/>
        <Option type="QString" value="collection" name="type"/>
      </Option>
    </data-defined-properties>
  </renderer-v2>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style
        fieldName="surface_elevation||' m'"
        isExpression="1"
        fontFamily="Arial"
        namedStyle="Bold"
        fontSize="10"
        fontSizeUnit="Point"
        textColor="255,0,0,255,rgb:1,0,0,1"
        textOpacity="1"
        fontItalic="0"
        fontUnderline="0"
        fontStrikeout="0"
        fontWeight="75"
        fontLetterSpacing="0"
        fontWordSpacing="0"
        fontKerning="1"
        capitalization="0"
        multilineHeight="1"
        multilineHeightUnit="Percentage"
        allowHtml="0"
        useSubstitutions="0"
        previewBkgrdColor="255,255,255,255,rgb:1,1,1,1"
        blendMode="0"
        legendString="Aa"
        stretchFactor="100"
        tabStopDistance="80"
        tabStopDistanceUnit="Point"
        tabStopDistanceMapUnitScale="3x:0,0,0,0,0,0"
        textOrientation="rotation-based"
        forcedBold="0"
        forcedItalic="0">
        <families/>
        <text-buffer
          bufferDraw="1"
          bufferSize="1"
          bufferSizeUnits="MM"
          bufferSizeMapUnitScale="3x:0,0,0,0,0,0"
          bufferColor="250,250,250,255,rgb:0.98,0.98,0.98,1"
          bufferNoFill="1"
          bufferOpacity="0.386"
          bufferJoinStyle="128"
          bufferBlendMode="0"/>
        <text-mask
          maskEnabled="0"
          maskType="0"
          maskSize="1.5"
          maskSize2="1.5"
          maskSizeUnits="MM"
          maskSizeMapUnitScale="3x:0,0,0,0,0,0"
          maskOpacity="1"
          maskJoinStyle="128"
          maskedSymbolLayers=""/>
        <background shapeDraw="0" shapeType="0" shapeOpacity="1"
          shapeBlendMode="0" shapeJoinStyle="64"
          shapeBorderColor="128,128,128,255,rgb:0.5,0.5,0.5,1"
          shapeBorderWidth="0" shapeBorderWidthUnit="Point"
          shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0"
          shapeFillColor="255,255,255,255,rgb:1,1,1,1"
          shapeOffsetX="0" shapeOffsetY="0" shapeOffsetUnit="Point"
          shapeOffsetMapUnitScale="3x:0,0,0,0,0,0"
          shapeRadiiX="0" shapeRadiiY="0" shapeRadiiUnit="Point"
          shapeRadiiMapUnitScale="3x:0,0,0,0,0,0"
          shapeSizeX="0" shapeSizeY="0" shapeSizeUnit="Point"
          shapeSizeMapUnitScale="3x:0,0,0,0,0,0"
          shapeSizeType="0" shapeRotation="0" shapeRotationType="0">
          <symbol type="marker" clip_to_extent="1" force_rhr="0" is_animated="0"
            frame_rate="10" alpha="1" name="markerSymbol">
            <data_defined_properties>
              <Option type="Map">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
            </data_defined_properties>
            <layer id="" enabled="1" pass="0" locked="0" class="SimpleMarker">
              <Option type="Map">
                <Option type="QString" value="0" name="angle"/>
                <Option type="QString" value="square" name="cap_style"/>
                <Option type="QString" value="190,178,151,255" name="color"/>
                <Option type="QString" value="1" name="horizontal_anchor_point"/>
                <Option type="QString" value="bevel" name="joinstyle"/>
                <Option type="QString" value="circle" name="name"/>
                <Option type="QString" value="0,0" name="offset"/>
                <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
                <Option type="QString" value="MM" name="offset_unit"/>
                <Option type="QString" value="35,35,35,255" name="outline_color"/>
                <Option type="QString" value="solid" name="outline_style"/>
                <Option type="QString" value="0" name="outline_width"/>
                <Option type="QString" value="3x:0,0,0,0,0,0" name="outline_width_map_unit_scale"/>
                <Option type="QString" value="MM" name="outline_width_unit"/>
                <Option type="QString" value="diameter" name="scale_method"/>
                <Option type="QString" value="2" name="size"/>
                <Option type="QString" value="3x:0,0,0,0,0,0" name="size_map_unit_scale"/>
                <Option type="QString" value="MM" name="size_unit"/>
                <Option type="QString" value="1" name="vertical_anchor_point"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option type="QString" value="" name="name"/>
                  <Option name="properties"/>
                  <Option type="QString" value="collection" name="type"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
          <symbol type="fill" clip_to_extent="1" force_rhr="0" is_animated="0"
            frame_rate="10" alpha="1" name="fillSymbol">
            <data_defined_properties>
              <Option type="Map">
                <Option type="QString" value="" name="name"/>
                <Option name="properties"/>
                <Option type="QString" value="collection" name="type"/>
              </Option>
            </data_defined_properties>
            <layer id="" enabled="1" pass="0" locked="0" class="SimpleFill">
              <Option type="Map">
                <Option type="QString" value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale"/>
                <Option type="QString" value="255,255,255,255" name="color"/>
                <Option type="QString" value="bevel" name="joinstyle"/>
                <Option type="QString" value="0,0" name="offset"/>
                <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
                <Option type="QString" value="MM" name="offset_unit"/>
                <Option type="QString" value="128,128,128,255" name="outline_color"/>
                <Option type="QString" value="no" name="outline_style"/>
                <Option type="QString" value="0" name="outline_width"/>
                <Option type="QString" value="Point" name="outline_width_unit"/>
                <Option type="QString" value="solid" name="style"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option type="QString" value="" name="name"/>
                  <Option name="properties"/>
                  <Option type="QString" value="collection" name="type"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </background>
        <shadow shadowDraw="0" shadowColor="0,0,0,255,rgb:0,0,0,1"
          shadowRadius="1.5" shadowRadiusUnit="MM"
          shadowRadiusMapUnitScale="3x:0,0,0,0,0,0"
          shadowRadiusAlphaOnly="0" shadowOpacity="0.7"
          shadowOffsetDist="1" shadowOffsetAngle="135"
          shadowOffsetUnit="MM" shadowOffsetMapUnitScale="3x:0,0,0,0,0,0"
          shadowOffsetGlobal="1" shadowScale="100" shadowUnder="0"
          shadowBlendMode="6"/>
        <dd_properties>
          <Option type="Map">
            <Option type="QString" value="" name="name"/>
            <Option name="properties"/>
            <Option type="QString" value="collection" name="type"/>
          </Option>
        </dd_properties>
        <substitutions/>
      </text-style>
      <text-format
        wrapChar=""
        formatNumbers="0"
        decimals="3"
        plussign="0"
        leftDirectionSymbol="&lt;"
        rightDirectionSymbol=">"
        placeDirectionSymbol="0"
        addDirectionSymbol="0"
        reverseDirectionSymbol="0"
        autoWrapLength="0"
        useMaxLineLengthForAutoWrap="1"
        multilineAlign="0"/>
      <placement
        placement="2"
        placementFlags="9"
        dist="0"
        distUnits="MM"
        distMapUnitScale="3x:0,0,0,0,0,0"
        offsetType="0"
        offsetUnits="MM"
        labelOffsetMapUnitScale="3x:0,0,0,0,0,0"
        xOffset="0"
        yOffset="0"
        rotationAngle="0"
        rotationUnit="AngleDegrees"
        preserveRotation="0"
        repeatDistance="0"
        repeatDistanceUnits="MM"
        repeatDistanceMapUnitScale="3x:0,0,0,0,0,0"
        maxCurvedCharAngleIn="25"
        maxCurvedCharAngleOut="-25"
        priority="10"
        centroidWhole="0"
        centroidInside="0"
        fitInPolygonOnly="0"
        overrunDistance="0"
        overrunDistanceUnit="MM"
        overrunDistanceMapUnitScale="3x:0,0,0,0,0,0"
        maximumDistance="0"
        maximumDistanceUnit="MM"
        maximumDistanceMapUnitScale="3x:0,0,0,0,0,0"
        lineAnchorPercent="0.5"
        lineAnchorType="0"
        lineAnchorClipping="1"
        lineAnchorTextPoint="FollowPlacement"
        polygonPlacementFlags="2"
        quadOffset="4"
        predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR"
        layerType="LineGeometry"
        geometryGenerator=""
        geometryGeneratorEnabled="0"
        geometryGeneratorType="PointGeometry"
        overlapHandling="AllowOverlapAtNoCost"
        allowDegraded="0"
        prioritization="PreferCloser"/>
      <rendering
        drawLabels="1"
        upsidedownLabels="1"
        minFeatureSize="0"
        fontMinPixelSize="3"
        fontMaxPixelSize="10000"
        fontLimitPixelSize="0"
        scaleVisibility="0"
        scaleMin="0"
        scaleMax="0"
        limitNumLabels="0"
        maxNumLabels="2000"
        obstacleType="1"
        obstacleFactor="2"
        obstacle="1"
        zIndex="0"
        labelPerPart="0"
        mergeLines="0"
        unplacedVisibility="0"/>
      <dd_properties>
        <Option type="Map">
          <Option type="QString" value="" name="name"/>
          <Option type="Map" name="properties">
            <Option type="Map" name="LabelRotation">
              <Option type="bool" value="false" name="active"/>
              <Option type="QString" value="45" name="expression"/>
              <Option type="int" value="3" name="type"/>
            </Option>
          </Option>
          <Option type="QString" value="collection" name="type"/>
        </Option>
      </dd_properties>
      <callout type="simple">
        <Option type="Map">
          <Option type="QString" value="pole_of_inaccessibility" name="anchorPoint"/>
          <Option type="int" value="0" name="blendMode"/>
          <Option type="Map" name="ddProperties">
            <Option type="QString" value="" name="name"/>
            <Option name="properties"/>
            <Option type="QString" value="collection" name="type"/>
          </Option>
          <Option type="bool" value="false" name="drawToAllParts"/>
          <Option type="QString" value="0" name="enabled"/>
          <Option type="QString" value="point_on_exterior" name="labelAnchorPoint"/>
          <Option type="double" value="0" name="minLength"/>
          <Option type="QString" value="3x:0,0,0,0,0,0" name="minLengthMapUnitScale"/>
          <Option type="QString" value="MM" name="minLengthUnit"/>
          <Option type="double" value="0" name="offsetFromAnchor"/>
          <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromAnchorMapUnitScale"/>
          <Option type="QString" value="MM" name="offsetFromAnchorUnit"/>
          <Option type="double" value="0" name="offsetFromLabel"/>
          <Option type="QString" value="3x:0,0,0,0,0,0" name="offsetFromLabelMapUnitScale"/>
          <Option type="QString" value="MM" name="offsetFromLabelUnit"/>
        </Option>
      </callout>
    </settings>
  </labeling>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
  <layerOpacity>1</layerOpacity>
  <geometryOptions geometryPrecision="0" removeDuplicateNodes="0">
    <activeChecks type="StringList">
      <Option type="QString" value=""/>
    </activeChecks>
    <checkConfiguration/>
  </geometryOptions>
  <legend type="default-vector" showLabelLegend="0"/>
  <referencedLayers/>
  <referencingLayers/>
  <fieldConfiguration>
    <field configurationFlags="NoFlag" name="ID">
      <editWidget type="Range">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field configurationFlags="NoFlag" name="surface_elevation">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <aliases>
    <alias index="0" field="ID" name=""/>
    <alias index="1" field="surface_elevation" name=""/>
  </aliases>
  <defaults>
    <default expression="" field="ID" applyOnUpdate="0"/>
    <default expression="" field="surface_elevation" applyOnUpdate="0"/>
  </defaults>
  <constraints>
    <constraint notnull_strength="0" unique_strength="0" exp_strength="0" field="ID" constraints="0"/>
    <constraint notnull_strength="0" unique_strength="0" exp_strength="0" field="surface_elevation" constraints="0"/>
  </constraints>
  <constraintExpressions>
    <constraint exp="" field="ID" desc=""/>
    <constraint exp="" field="surface_elevation" desc=""/>
  </constraintExpressions>
  <expressionfields/>
  <attributeactions>
    <defaultAction value="{00000000-0000-0000-0000-000000000000}" key="Canvas"/>
  </attributeactions>
  <attributetableconfig sortOrder="0" sortExpression="" actionWidgetStyle="dropDown">
    <columns>
      <column type="field" hidden="0" width="-1" name="ID"/>
      <column type="field" hidden="0" width="-1" name="surface_elevation"/>
      <column type="actions" hidden="1" width="-1"/>
    </columns>
  </attributetableconfig>
  <conditionalstyles>
    <rowstyles/>
    <fieldstyles/>
  </conditionalstyles>
  <storedexpressions/>
  <editform tolerant="1"></editform>
  <editforminit/>
  <editforminitcodesource>0</editforminitcodesource>
  <editforminitfilepath></editforminitfilepath>
  <editforminitcode><![CDATA[# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QWidget
def my_form_open(dialog, layer, feature):
    pass
]]></editforminitcode>
  <featformsuppress>0</featformsuppress>
  <editorlayout>generatedlayout</editorlayout>
  <editable>
    <field editable="1" name="ID"/>
    <field editable="1" name="surface_elevation"/>
  </editable>
  <labelOnTop>
    <field labelOnTop="0" name="ID"/>
    <field labelOnTop="0" name="surface_elevation"/>
  </labelOnTop>
  <reuseLastValue>
    <field reuseLastValue="0" name="ID"/>
    <field reuseLastValue="0" name="surface_elevation"/>
  </reuseLastValue>
  <dataDefinedFieldProperties/>
  <widgets/>
  <previewExpression>"ID"</previewExpression>
  <mapTip enabled="1"></mapTip>
  <layerGeometryType>1</layerGeometryType>
</qgis>
