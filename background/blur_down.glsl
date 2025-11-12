#version 330 core
out vec4 FragColor;
in vec2 TexCoords;
uniform sampler2D image;
uniform vec2 offset;

void main() {
    vec3 color = vec3(0.0);
    color += texture(image, TexCoords).rgb * 4.0;
    color += texture(image, TexCoords - offset).rgb;
    color += texture(image, TexCoords + offset).rgb;
    color += texture(image, TexCoords + vec2(offset.x, -offset.y)).rgb;
    color += texture(image, TexCoords - vec2(offset.x, -offset.y)).rgb;
    FragColor = vec4(color / 8.0, 1.0);
}
