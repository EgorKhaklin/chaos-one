using UnityEngine;

namespace ChaosOne.Threats
{
    [CreateAssetMenu(
        menuName = "ChaosOne/Threat Archetype",
        fileName = "ThreatArchetype",
        order = 100)]
    public sealed class ThreatArchetype : ScriptableObject
    {
        [Header("Identity")]
        [SerializeField] private string displayName = "HGV";
        [SerializeField] private ThreatClass classKind = ThreatClass.HypersonicGlideVehicle;

        [Header("Visuals")]
        [SerializeField] private Mesh hullMesh;
        [SerializeField] private Material hullMaterial;
        [SerializeField, ColorUsage(showAlpha: true, hdr: true)]
        private Color envelopeBaseColor = new(1.0f, 0.66f, 0.38f, 0.85f);
        [SerializeField, ColorUsage(showAlpha: true, hdr: true)]
        private Color trailColorHighAltitude = new(0.45f, 0.85f, 1.0f, 1.0f);
        [SerializeField, ColorUsage(showAlpha: true, hdr: true)]
        private Color trailColorLowAltitude = new(1.0f, 0.55f, 0.20f, 1.0f);

        [Header("Kinematics")]
        [SerializeField] private float minSpeedMps = 1500f;
        [SerializeField] private float maxSpeedMps = 6800f;
        [SerializeField] private float baseRcsM2 = 0.05f;

        [Header("Trust Model")]
        [SerializeField] private AnimationCurve trustDecayBySeconds =
            AnimationCurve.Linear(0f, 1f, 30f, 0.4f);

        public string DisplayName => displayName;
        public ThreatClass ClassKind => classKind;
        public Mesh HullMesh => hullMesh;
        public Material HullMaterial => hullMaterial;
        public Color EnvelopeBaseColor => envelopeBaseColor;
        public Color TrailColorHighAltitude => trailColorHighAltitude;
        public Color TrailColorLowAltitude => trailColorLowAltitude;
        public float MinSpeedMps => minSpeedMps;
        public float MaxSpeedMps => maxSpeedMps;
        public float BaseRcsM2 => baseRcsM2;
        public AnimationCurve TrustDecayBySeconds => trustDecayBySeconds;
    }
}
