Shader "ChaosOne/Trail"
{
    Properties
    {
        [HDR] _ColorHighAlt        ("High Altitude Color (HDR)", Color) = (0.45, 0.85, 1.00, 1.0)
        [HDR] _ColorLowAlt         ("Low Altitude Color (HDR)",  Color) = (1.00, 0.55, 0.20, 1.0)
        _AltitudeBlendKm           ("Altitude Blend (km)",       Range(1, 80)) = 20.0
        _EmissiveIntensity         ("Emissive Intensity",        Range(0, 12)) = 4.0
        _TipFalloff                ("Tip Falloff",               Range(0, 1)) = 0.85
    }

    SubShader
    {
        Tags
        {
            "RenderType"     = "Transparent"
            "Queue"          = "Transparent+60"
            "IgnoreProjector"= "True"
        }

        Pass
        {
            Name "TrailEmissive"

            Blend SrcAlpha One
            ZWrite Off
            Cull Off

            CGPROGRAM
            #pragma vertex   vert
            #pragma fragment frag
            #pragma target   3.0
            #include "UnityCG.cginc"

            float4 _ColorHighAlt;
            float4 _ColorLowAlt;
            float  _AltitudeBlendKm;
            float  _EmissiveIntensity;
            float  _TipFalloff;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float4 color      : COLOR;
                float2 uv         : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float  altitudeKm : TEXCOORD0;
                float  ageT       : TEXCOORD1;
                float4 vertColor  : COLOR;
            };

            Varyings vert (Attributes IN)
            {
                Varyings OUT;
                float3 worldPos    = mul(unity_ObjectToWorld, IN.positionOS).xyz;
                OUT.positionCS     = UnityObjectToClipPos(IN.positionOS);
                OUT.altitudeKm     = worldPos.y / 1000.0;
                OUT.ageT           = IN.uv.x;
                OUT.vertColor      = IN.color;
                return OUT;
            }

            float4 frag (Varyings IN) : SV_TARGET
            {
                float  blend     = saturate(IN.altitudeKm / _AltitudeBlendKm);
                float3 ambientCol= lerp(_ColorLowAlt.rgb, _ColorHighAlt.rgb, blend);
                float3 finalCol  = ambientCol * IN.vertColor.rgb * _EmissiveIntensity;

                float  tipMask   = 1.0 - pow(1.0 - saturate(IN.ageT), _TipFalloff + 1.0);
                float  alpha     = IN.vertColor.a * tipMask;

                return float4(finalCol, alpha);
            }
            ENDCG
        }
    }

    FallBack Off
}
