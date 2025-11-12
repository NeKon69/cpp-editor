#version 330 core
out vec4 FragColor;
in vec2 TexCoords;
uniform sampler2D image;
uniform vec2 offset;

void main() {
    vec3 color = vec3(0.0);
    color += texture(image, TexCoords + vec2(-offset.x * 2.0, 0.0)).rgb;
    color += texture(image, TexCoords + vec2(-offset.x, offset.y)).rgb * 2.0;
    color += texture(image, TexCoords + vec2(0.0, offset.y * 2.0)).rgb;
    color += texture(image, TexCoords + vec2(offset.x, offset.y)).rgb * 2.0;
    color += texture(image, TexCoords + vec2(offset.x * 2.0, 0.0)).rgb;
    color += texture(image, TexCoords + vec2(offset.x, -offset.y)).rgb * 2.0;
    color += texture(image, TexCoords + vec2(0.0, -offset.y * 2.0)).rgb;
    color += texture(image, TexCoords + vec2(-offset.x, -offset.y)).rgb * 2.0;
    FragColor = vec4(color / 12.0, 1.0);
}
