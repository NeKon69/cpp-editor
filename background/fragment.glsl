#version 330

#define USE_CHROMATIC_ABERRATION 1
#define CHROMATIC_ABERRATION_STRENGTH 0.05

#define PROCEDURAL_FLOW_STRENGTH 0.05
#define DOMAIN_WARP_INTENSITY 2.5
#define TEXTURE_WARP_STRENGTH 0.04

#define USE_GOD_RAYS 1
#define GOD_RAYS_SAMPLES 100
#define GOD_RAYS_DENSITY 0.6
#define GOD_RAYS_WEIGHT 0.5
#define GOD_RAYS_EXPOSURE 1.5
const vec2 godRaysLightPosition = vec2(0.5, 0.5);
#define USE_FILM_GRAIN 1
#define FILM_GRAIN_STRENGTH 0.04

const float TEXTURE_WARP_STRENGTH_HALF = TEXTURE_WARP_STRENGTH * 0.5;

precision mediump float;
uniform sampler2D iChannel0;
out vec4 outColor;
uniform vec2 ViewportSize;
uniform float Time;

#define ZOOM 0.7

vec2 hash(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}
float noise(in vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(dot(hash(i + vec2(0.0, 0.0)), f - vec2(0.0, 0.0)),
            dot(hash(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0)), u.x),
        mix(dot(hash(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0)),
            dot(hash(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0)), u.x), u.y);
}
mat2 m = mat2(0.8, 0.6, -0.6, 0.8);
float fbm(vec2 p) {
    float f = 0.0;
    f += 0.5000 * noise(p);
    p = m * p * 2.02;
    f += 0.2500 * noise(p);
    return f / 0.75;
}
float fbm_anti_tiling(vec2 p) {
    float val = 0.0;
    val += fbm(p) * 0.5;
    val += fbm(p * 2.2 + 123.45) * 0.25;
    val += fbm(p * 0.7 - 54.32) * 0.25;
    return val;
}

#if USE_FILM_GRAIN == 1
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}
#endif

void main()
{
    highp vec2 uv = gl_FragCoord.xy / ViewportSize.y * ZOOM;
    float time_flow = Time * 0.15;
    float time_warp = Time * 0.3;
    vec2 flow1_uv = uv * 1.2 + time_flow;
    vec2 flow1 = vec2(fbm_anti_tiling(flow1_uv), fbm_anti_tiling(flow1_uv + vec2(5.2, 1.3)));
    vec2 flow2_uv = flow1 * DOMAIN_WARP_INTENSITY + (uv * 2.0 - time_flow * 0.5);
    vec2 flow2 = vec2(fbm_anti_tiling(flow2_uv), fbm_anti_tiling(flow2_uv + vec2(8.3, 2.8)));
    vec2 proceduralDistortion = (flow1 + flow2) * PROCEDURAL_FLOW_STRENGTH;
    vec2 warped_uv = uv + proceduralDistortion;
    vec2 tex_warp_uv1 = warped_uv * 3.3 + vec2(0.0, time_warp * 0.2);
    vec2 tex_warp_uv2 = warped_uv * 2.1 + vec2(time_warp * 0.2, 0.0);
    vec2 warp1 = texture(iChannel0, tex_warp_uv1).rg;
    vec2 warp2 = texture(iChannel0, tex_warp_uv2).rg;
    vec2 textureWarp = warp1 * TEXTURE_WARP_STRENGTH - warp2 * TEXTURE_WARP_STRENGTH_HALF;
    vec2 finalTextureDistortion = textureWarp - 2.0;
    vec2 totalDistortion = proceduralDistortion + finalTextureDistortion;
    vec2 finalUV = uv + totalDistortion;

    vec3 finalColor;

    #if USE_CHROMATIC_ABERRATION == 1
    vec2 offset = totalDistortion * CHROMATIC_ABERRATION_STRENGTH;
    float r = texture(iChannel0, finalUV + offset).r;
    float g = texture(iChannel0, finalUV).g;
    float b = texture(iChannel0, finalUV - offset).b;
    finalColor = 0.5 + 0.5 * cos(vec3(r, g, b) * 3.14159 - 2.6);
    #else
    vec3 texColor = texture(iChannel0, finalUV).rgb;
    finalColor = 0.5 + 0.5 * cos(texColor * 3.14159);
    #endif

    vec3 postProcessedColor = finalColor;

    #if USE_GOD_RAYS == 1
    vec2 screnSpaceUV = gl_FragCoord.xy / ViewportSize;
    vec2 delta = godRaysLightPosition - screnSpaceUV;
    float dist = length(delta);
    vec2 step = delta / float(GOD_RAYS_SAMPLES);
    float illuminationDecay = 1.0;

    vec3 godRaysColor = vec3(0.0);

    for (int i = 0; i < GOD_RAYS_SAMPLES; i++)
    {
        screnSpaceUV += step;
        vec3 sampleColor = texture(iChannel0, screnSpaceUV * (ViewportSize.y / ViewportSize.x * ZOOM, ZOOM) + totalDistortion).rgb;
        sampleColor *= illuminationDecay * GOD_RAYS_WEIGHT;
        godRaysColor += sampleColor;
        illuminationDecay *= GOD_RAYS_DENSITY;
    }

    postProcessedColor += pow(godRaysColor, vec3(GOD_RAYS_EXPOSURE));
    #endif

    #if USE_FILM_GRAIN == 1
    postProcessedColor += (random(uv * Time) - 0.5) * FILM_GRAIN_STRENGTH;
    #endif

    outColor = vec4(postProcessedColor, 1.0);
}
