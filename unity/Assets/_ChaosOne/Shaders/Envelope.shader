Shader "ChaosOne/Envelope"
{
    Properties
    {
        [HDR] _BaseColor          ("Base Color (HDR)",        Color)         = (1.00, 0.66, 0.38, 0.85)
        _Confidence               ("Confidence (0..1)",       Range(0, 1))   = 1.0
        _DisagreementStripes      ("Disagreement Stripes",    Range(0, 32))  = 0
        _StripeBrightness         ("Stripe Brightness",       Range(0, 1))   = 0.55
        _RimPower                 ("Rim Power",               Range(0.25, 8))= 3.0
        _AlphaScale               ("Alpha Scale",             Range(0, 1))   = 0.85
        _EmissiveIntensity        ("Emissive Intensity",      Range(0, 8))   = 2.5
        _StateTint                ("State Tint",              Color)         = (1, 1, 1, 1)
    }

    SubShader
    {
        Tags
        {
            "RenderType"     = "Transparent"
            "Queue"          = "Transparent+50"
            "IgnoreProjector"= "True"
            "PreviewType"    = "Plane"
        }

        Pass
        {
            Name "EnvelopeUnlit"

            Blend SrcAlpha One
            ZWrite Off
            Cull Back

            CGPROGRAM
            #pragma vertex   vert
            #pragma fragment frag
            #pragma target   3.0

            #include "UnityCG.cginc"

            float4 _BaseColor;
            float4 _StateTint;
            float  _Confidence;
            float  _DisagreementStripes;
            float  _StripeBrightness;
            float  _RimPower;
            float  _AlphaScale;
            float  _EmissiveIntensity;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float2 uv         : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 normalWS   : TEXCOORD0;
                float3 viewDirWS  : TEXCOORD1;
                float2 uv         : TEXCOORD2;
            };

            Varyings vert (Attributes IN)
            {
                Varyings OUT;
                float3 worldPos = mul(unity_ObjectToWorld, IN.positionOS).xyz;
                OUT.positionCS  = UnityObjectToClipPos(IN.positionOS);
                OUT.normalWS    = UnityObjectToWorldNormal(IN.normalOS);
                OUT.viewDirWS   = normalize(_WorldSpaceCameraPos - worldPos);
                OUT.uv          = IN.uv;
                return OUT;
            }

            // Two-band procedural stripe driven by surface UV.v.
            // Returns 1.0 when no disagreement; oscillates between
            // _StripeBrightness and 1.0 when disagreement is set.
            float stripe_mask (float2 uv, float stripeCount)
            {
                if (stripeCount < 0.5)
                    return 1.0;

                float band  = frac(uv.y * stripeCount);
                float mask  = step(0.5, band);
                return lerp(_StripeBrightness, 1.0, mask);
            }

            float4 frag (Varyings IN) : SV_TARGET
            {
                float3 n         = normalize(IN.normalWS);
                float3 v         = normalize(IN.viewDirWS);
                float  ndotv     = saturate(dot(n, v));
                float  rim       = pow(1.0 - ndotv, _RimPower);

                float  stripe    = stripe_mask(IN.uv, _DisagreementStripes);
                float  saturation= lerp(0.45, 1.0, saturate(_Confidence));

                float3 baseRgb   = _BaseColor.rgb * _StateTint.rgb * saturation * stripe;
                float3 emissive  = baseRgb * _EmissiveIntensity;

                float  alpha     = rim * _AlphaScale * _BaseColor.a;
                return float4(emissive, alpha);
            }
            ENDCG
        }
    }

    FallBack Off
}
