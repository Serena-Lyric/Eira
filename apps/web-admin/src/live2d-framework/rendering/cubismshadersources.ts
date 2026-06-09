// @ts-nocheck
/**
 * Eira: Cubism 着色器源码内联（替代运行时 fetch）。
 * 由 public/live2d-core/shaders/ 的官方文件生成，使用 String.raw 模板字面量。
 * 原因：运行时 fetch 相对路径在 SPA 路由下解析为 HTML(404)，导致 GLSL 编译失败。
 */

export const VERT_SRC = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


attribute vec4 a_position;
attribute vec2 a_texCoord;
varying vec2 v_texCoord;
uniform mat4 u_matrix;

void main()
{
    gl_Position = u_matrix * a_position;
    v_texCoord = a_texCoord;
    v_texCoord.y = 1.0 - v_texCoord.y;
}
`;

export const VERT_SRC_MASKED = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


attribute vec4 a_position;
attribute vec2 a_texCoord;
varying vec2 v_texCoord;
varying vec4 v_clipPos;
uniform mat4 u_matrix;
uniform mat4 u_clipMatrix;

void main()
{
    gl_Position = u_matrix * a_position;
    v_clipPos = u_clipMatrix * a_position;
    v_texCoord = a_texCoord;
    v_texCoord.y = 1.0 - v_texCoord.y;
}
`;

export const VERT_SRC_SETUP_MASK = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


attribute vec4 a_position;
attribute vec2 a_texCoord;
varying vec2 v_texCoord;
varying vec4 v_myPos;
uniform mat4 u_clipMatrix;

void main()
{
    gl_Position = u_clipMatrix * a_position;
    v_myPos = u_clipMatrix * a_position;
    v_texCoord = a_texCoord;
    v_texCoord.y = 1.0 - v_texCoord.y;
}
`;

export const FRAG_SRC_SETUP_MASK = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


precision mediump float;
varying vec2 v_texCoord; //v2f.texcoord
varying vec4 v_myPos;
uniform vec4 u_baseColor; //v2f.color
uniform vec4 u_channelFlag;
uniform sampler2D s_texture0; //_MainTex


void main()
{
  float isInside =
    step(u_baseColor.x, v_myPos.x/v_myPos.w)
    * step(u_baseColor.y, v_myPos.y/v_myPos.w)
    * step(v_myPos.x/v_myPos.w, u_baseColor.z)
    * step(v_myPos.y/v_myPos.w, u_baseColor.w);
  gl_FragColor = u_channelFlag * texture2D(s_texture0, v_texCoord).a * isInside;
}
`;

export const FRAG_SRC_PREMULT_ALPHA = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


precision mediump float;
varying vec2 v_texCoord; //v2f.texcoord
uniform vec4 u_baseColor; //v2f.color
uniform sampler2D s_texture0; //_MainTex
uniform vec4 u_multiplyColor;
uniform vec4 u_screenColor;

void main()
{
  vec4 texColor = texture2D(s_texture0, v_texCoord);
  texColor.rgb = texColor.rgb * u_multiplyColor.rgb;
  texColor.rgb = (texColor.rgb + u_screenColor.rgb * texColor.a) - (texColor.rgb * u_screenColor.rgb);
  vec4 color = texColor * u_baseColor;
  gl_FragColor = vec4(color.rgb, color.a);
}
`;

export const FRAG_SRC_MASK_PREMULT_ALPHA = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


precision mediump float;
varying vec2 v_texCoord; //v2f.texcoord
varying vec4 v_clipPos;
uniform vec4 u_baseColor; //v2f.color
uniform vec4 u_channelFlag;
uniform sampler2D s_texture0; //_MainTex
uniform sampler2D s_texture1; // _ClippingMaskTex
uniform vec4 u_multiplyColor;
uniform vec4 u_screenColor;

void main()
{
  vec4 texColor = texture2D(s_texture0, v_texCoord);
  texColor.rgb = texColor.rgb * u_multiplyColor.rgb;
  texColor.rgb = (texColor.rgb + u_screenColor.rgb * texColor.a) - (texColor.rgb * u_screenColor.rgb);
  vec4 col_formask = texColor * u_baseColor;
  vec4 clipMask = (1.0 - texture2D(s_texture1, v_clipPos.xy / v_clipPos.w)) * u_channelFlag;
  float maskVal = clipMask.r + clipMask.g + clipMask.b + clipMask.a;
  col_formask = col_formask * maskVal;
  gl_FragColor = col_formask;
}
`;

export const FRAG_SRC_MASK_INV_PREMULT_ALPHA = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


precision mediump float;
varying vec2 v_texCoord; //v2f.texcoord
varying vec4 v_clipPos;
uniform sampler2D s_texture0; //_MainTex
uniform sampler2D s_texture1; // _ClippingMaskTex
uniform vec4 u_channelFlag;
uniform vec4 u_baseColor; //v2f.color
uniform vec4 u_multiplyColor;
uniform vec4 u_screenColor;

void main()
{
  vec4 texColor = texture2D(s_texture0, v_texCoord);
  texColor.rgb = texColor.rgb * u_multiplyColor.rgb;
  texColor.rgb = (texColor.rgb + u_screenColor.rgb * texColor.a) - (texColor.rgb * u_screenColor.rgb);
  vec4 col_formask = texColor * u_baseColor;
  vec4 clipMask = (1.0 - texture2D(s_texture1, v_clipPos.xy / v_clipPos.w)) * u_channelFlag;
  float maskVal = clipMask.r + clipMask.g + clipMask.b + clipMask.a;
  col_formask = col_formask * (1.0 - maskVal);
  gl_FragColor = col_formask;
}
`;

export const VERT_SRC_COPY = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


attribute vec4 a_position;
attribute vec2 a_texCoord;
varying vec2 v_texCoord;

void main()
{
    v_texCoord = a_texCoord;
    gl_Position = a_position;
}
`;

export const FRAG_SRC_COPY = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


precision mediump float;

varying vec2 v_texCoord;
uniform vec4 u_baseColor;
uniform sampler2D s_texture0;

void main()
{
    gl_FragColor = texture2D(s_texture0, v_texCoord) * u_baseColor;
}
`;

export const FRAG_SRC_COLOR_BLEND = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


#if defined(COLOR_BLEND_NORMAL)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return colorSource;
}

#elif defined(COLOR_BLEND_ADDCOMPATIBLE)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(0.0);
}

#elif defined(COLOR_BLEND_MULTCOMPATIBLE)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(0.0);
}

#elif defined(COLOR_BLEND_ADD)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return min(colorSource + colorDestination, 1.0);
}

#elif defined(COLOR_BLEND_ADDGLOW)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return colorSource + colorDestination;
}

#elif defined(COLOR_BLEND_DARKEN)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return min(colorSource, colorDestination);
}

#elif defined(COLOR_BLEND_MULTIPLY)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return colorSource * colorDestination;
}

#elif defined(COLOR_BLEND_COLORBURN)
float ColorBurn(float colorSource, float colorDestination)
{
    if (abs(colorDestination - 1.0) < 0.000001)
    {
        return 1.0;
    }
    else if (abs(colorSource) < 0.000001)
    {
        return 0.0;
    }

    return 1.0 - min(1.0, (1.0 - colorDestination) / colorSource);
}

vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(
        ColorBurn(colorSource.r, colorDestination.r),
        ColorBurn(colorSource.g, colorDestination.g),
        ColorBurn(colorSource.b, colorDestination.b)
    );
}

#elif defined(COLOR_BLEND_LINEARBURN)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return max(vec3(0.0), colorSource + colorDestination - 1.0);
}

#elif defined(COLOR_BLEND_LIGHTEN)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return max(colorSource, colorDestination);
}

#elif defined(COLOR_BLEND_SCREEN)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return colorSource + colorDestination - colorSource * colorDestination;
}

#elif defined(COLOR_BLEND_COLORDODGE)
float ColorDodge(float colorSource, float colorDestination)
{
    if (colorDestination <= 0.0)
    {
        return 0.0;
    }
    else if (colorSource == 1.0)
    {
        return 1.0;
    }

    return min(1.0, colorDestination / (1.0 - colorSource));
}

vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(
        ColorDodge(colorSource.r, colorDestination.r),
        ColorDodge(colorSource.g, colorDestination.g),
        ColorDodge(colorSource.b, colorDestination.b)
    );
}

#elif defined(COLOR_BLEND_OVERLAY)
float Overlay(float colorSource, float colorDestination)
{
    float mul = 2.0 * colorSource * colorDestination;
    float scr = 1.0 - 2.0 * (1.0 - colorSource) * (1.0 - colorDestination) ;
    return colorDestination < 0.5 ? mul : scr ;
}

vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(
        Overlay(colorSource.r, colorDestination.r),
        Overlay(colorSource.g, colorDestination.g),
        Overlay(colorSource.b, colorDestination.b)
    );
}

#elif defined(COLOR_BLEND_SOFTLIGHT)
float SoftLight(float colorSource, float colorDestination)
{
    float val1 = colorDestination - (1.0 - 2.0 * colorSource) * colorDestination * (1.0 - colorDestination);
    float val2 = colorDestination + (2.0 * colorSource - 1.0) * colorDestination * ((16.0 * colorDestination - 12.0) * colorDestination + 3.0);
    float val3 = colorDestination + (2.0 * colorSource - 1.0) * (sqrt(colorDestination) - colorDestination);

    if (colorSource <= 0.5)
    {
        return val1;
    }
    else if (colorDestination <= 0.25)
    {
        return val2;
    }

    return val3;
}

vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(
        SoftLight(colorSource.r, colorDestination.r),
        SoftLight(colorSource.g, colorDestination.g),
        SoftLight(colorSource.b, colorDestination.b)
    );
}

#elif defined(COLOR_BLEND_HARDLIGHT)
float HardLight(float colorSource, float colorDestination)
{
    float mul = 2.0 * colorSource * colorDestination;
    float scr = 1.0 - 2.0 * (1.0 - colorSource) * (1.0 - colorDestination);

    if (colorSource < 0.5)
    {
        return mul;
    }

    return scr;
}

vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(
        HardLight(colorSource.r, colorDestination.r),
        HardLight(colorSource.g, colorDestination.g),
        HardLight(colorSource.b, colorDestination.b)
    );
}

#elif defined(COLOR_BLEND_LINEARLIGHT)
float LinearLight(float colorSource, float colorDestination)
{
    float burn = max(0.0, 2.0 * colorSource + colorDestination - 1.0);
    float dodge = min(1.0, 2.0 * (colorSource - 0.5) + colorDestination);

    if (colorSource < 0.5)
    {
        return burn;
    }

    return dodge;
}

vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return vec3(
        LinearLight(colorSource.r, colorDestination.r),
        LinearLight(colorSource.g, colorDestination.g),
        LinearLight(colorSource.b, colorDestination.b)
    );
}

#elif defined(COLOR_BLEND_HUE) || defined(COLOR_BLEND_COLOR)
const float rCoeff = 0.30;
const float gCoeff = 0.59;
const float bCoeff = 0.11;

float GetMax(vec3 rgbC)
{
    return max(rgbC.r, max(rgbC.g, rgbC.b));
}

float GetMin(vec3 rgbC)
{
    return min(rgbC.r, min(rgbC.g, rgbC.b));
}

float GetRange(vec3 rgbC)
{
    return max(rgbC.r, max(rgbC.g, rgbC.b)) - min(rgbC.r, min(rgbC.g, rgbC.b));
}

float Saturation(vec3 rgbC)
{
    return GetRange(rgbC);
}

float Luma(vec3 rgbC)
{
    return rCoeff * rgbC.r + gCoeff * rgbC.g + bCoeff * rgbC.b;
}

vec3 ClipColor(vec3 rgbC)
{
    float   luma = Luma(rgbC);
    float   maxv = GetMax(rgbC);
    float   minv = GetMin(rgbC);
    vec3    outputColor = rgbC;

    outputColor = minv < 0.0 ? luma + (outputColor - luma) * luma / (luma - minv) : outputColor;
    outputColor = maxv > 1.0 ? luma + (outputColor - luma) * (1.0 - luma) / (maxv - luma) : outputColor;

    return outputColor;
}

vec3 SetLuma(vec3 rgbC, float luma)
{
    return ClipColor(rgbC + (luma - Luma(rgbC)));
}

vec3 SetSaturation(vec3 rgbC, float saturation)
{
    float maxv = GetMax(rgbC);
    float minv = GetMin(rgbC);
    float medv = rgbC.r + rgbC.g + rgbC.b - maxv - minv;
    float outputMax, outputMed, outputMin;

    outputMax = minv < maxv ? saturation : 0.0;
    outputMed = minv < maxv ? (medv - minv) * saturation / (maxv - minv) : 0.0;
    outputMin = 0.0;

    if(rgbC.r == maxv)
    {
        return rgbC.b < rgbC.g ? vec3(outputMax, outputMed, outputMin) : vec3(outputMax, outputMin, outputMed);
    }
    else if(rgbC.g == maxv)
    {
        return rgbC.r < rgbC.b ? vec3(outputMin, outputMax, outputMed) : vec3(outputMed, outputMax, outputMin);
    }
    else // if(rgbC.b == maxv)
    {
        return rgbC.g < rgbC.r ? vec3(outputMed, outputMin, outputMax) : vec3(outputMin, outputMed, outputMax);
    }
}

#if defined(COLOR_BLEND_HUE)
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return SetLuma(SetSaturation(colorSource, Saturation(colorDestination)), Luma(colorDestination));
}

#else
vec3 ColorBlend(vec3 colorSource, vec3 colorDestination)
{
    return SetLuma(colorSource, Luma(colorDestination)) ;
}

#endif

#else
#error not supported color blend function.

#endif
`;

export const FRAG_SRC_ALPHA_BLEND = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


vec4 OverlapRgba(vec3 color, vec3 colorSource, vec3 colorDestination, vec3 parameter)
{
    vec3 rgb = color * parameter.x + colorSource * parameter.y + colorDestination * parameter.z;
    float alpha = parameter.x + parameter.y + parameter.z;
    return vec4(rgb, alpha);
}

#if defined(ALPHA_BLEND_OVER)
vec4 AlphaBlend(vec3 color, vec4 colorSource, vec4 colorDestination)
{
    vec3 parameter = vec3(colorSource.a * colorDestination.a, colorSource.a * (1.0 - colorDestination.a), colorDestination.a * (1.0 - colorSource.a));
    return OverlapRgba(color, colorSource.rgb, colorDestination.rgb, parameter);
}

#elif defined(ALPHA_BLEND_ATOP)
vec4 AlphaBlend(vec3 color, vec4 colorSource, vec4 colorDestination)
{
    vec3 parameter = vec3(colorSource.a * colorDestination.a, 0, colorDestination.a * (1.0 - colorSource.a));
    return OverlapRgba(color, colorSource.rgb, colorDestination.rgb, parameter);
}

#elif defined(ALPHA_BLEND_OUT)
vec4 AlphaBlend(vec3 color, vec4 colorSource, vec4 colorDestination)
{
    vec3 parameter = vec3(0.0, 0.0, colorDestination.a * (1.0 - colorSource.a));
    return OverlapRgba(color, colorSource.rgb, colorDestination.rgb, parameter);
}

#elif defined(ALPHA_BLEND_CONJOINTOVER)
vec4 AlphaBlend(vec3 color, vec4 colorSource, vec4 colorDestination)
{
    vec3 parameter = vec3(min(colorSource.a, colorDestination.a), max(colorSource.a - colorDestination.a, 0.0), max(colorDestination.a - colorSource.a, 0.0));
    return OverlapRgba(color, colorSource.rgb, colorDestination.rgb, parameter);
}

#elif defined(ALPHA_BLEND_DISJOINTOVER)
vec4 AlphaBlend(vec3 color, vec4 colorSource, vec4 colorDestination)
{
    vec3 parameter = vec3(max(colorSource.a + colorDestination.a - 1.0, 0.0), min(colorSource.a, 1.0 - colorDestination.a), min(colorDestination.a, 1.0 - colorSource.a));
    return OverlapRgba(color, colorSource.rgb, colorDestination.rgb, parameter);
}

#else
#error not supported alpha blend function

#endif
`;

export const VERT_SRC_BLEND = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


attribute vec4 a_position;
attribute vec2 a_texCoord;
varying vec2 v_texCoord;
varying vec2 v_blendCoord;
varying vec4 v_clipPos;
uniform mat4 u_matrix;
uniform mat4 u_clipMatrix;

void main()
{
    gl_Position = u_matrix * a_position;

#ifdef CLIPPING_MASK
    v_clipPos = u_clipMatrix * a_position;
#else
    v_clipPos = vec4(0.0);
#endif

    v_texCoord = a_texCoord;
    v_texCoord.y = 1.0 - v_texCoord.y;
    vec2 ndcPos = gl_Position.xy / gl_Position.w;
    v_blendCoord = ndcPos * 0.5 + 0.5;
}
`;

export const FRAG_SRC_PREMULT_ALPHA_BLEND = String.raw`
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */


varying vec2 v_texCoord; //v2f.texcoord
varying vec2 v_blendCoord;
varying vec4 v_clipPos;
uniform sampler2D s_texture0; //_MainTex
uniform sampler2D s_blendTexture;
uniform vec4 u_baseColor; //v2f.color
uniform vec4 u_multiplyColor;
uniform vec4 u_screenColor;
uniform sampler2D s_texture1; // _ClippingMaskTex
uniform float u_invertClippingMask;
uniform vec4 u_channelFlag;

vec3 ColorBlend(vec3 colorSource, vec3 colorDestination);
vec4 AlphaBlend(vec3 C, vec3 Cs, float As, vec3 Cd, float Ad);

void main()
{
  vec4 renderTextureColor = texture2D(s_blendTexture, v_blendCoord);
  vec3 colorDestination = renderTextureColor.rgb;
  float alphaDestination = renderTextureColor.a;

  if (alphaDestination < 0.00001)
  {
    colorDestination = vec3(0.0, 0.0, 0.0);
  }
  else {
    colorDestination /= alphaDestination;
  }

  vec4 texColor = texture2D(s_texture0, v_texCoord);
  texColor.rgb *= u_multiplyColor.rgb;
  texColor.rgb = (texColor.rgb + u_screenColor.rgb) - (texColor.rgb * u_screenColor.rgb);

  texColor *= u_baseColor;
  vec3 colorSource = texColor.rgb;
  float alphaSource = texColor.a;

  if (alphaSource < 0.00001)
  {
    colorSource = vec3(0.0, 0.0, 0.0);
  }
  else {
    colorSource /= alphaSource;
  }

#ifdef CLIPPING_MASK
    float maskVal = 1.0;
    vec4 clipMask = (1.0 - texture2D(s_texture1, v_clipPos.xy / v_clipPos.w)) * u_channelFlag;
    maskVal = clipMask.r + clipMask.g + clipMask.b + clipMask.a;
    maskVal = abs(u_invertClippingMask - maskVal);

    alphaSource *= maskVal;
#endif

  vec4 source = vec4(colorSource.r, colorSource.g, colorSource.b, alphaSource);
  vec4 destination = vec4(colorDestination.r, colorDestination.g, colorDestination.b, alphaDestination);

  gl_FragColor = AlphaBlend(ColorBlend(colorSource, colorDestination), source, destination);
}
`;

