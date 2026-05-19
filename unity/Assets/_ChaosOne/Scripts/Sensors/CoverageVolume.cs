using UnityEngine;

namespace ChaosOne.Sensors
{
    /// <summary>
    /// Visualizes a sensor's coverage as a translucent volume. Trust weight
    /// and spoof flag drive shader uniforms through a MaterialPropertyBlock,
    /// so multiple coverage volumes can share one material without allocations.
    /// </summary>
    [RequireComponent(typeof(MeshRenderer))]
    public sealed class CoverageVolume : MonoBehaviour
    {
        [SerializeField, ColorUsage(showAlpha: true, hdr: true)]
        private Color baseColor = new(0.40f, 0.85f, 1.00f, 0.55f);

        [SerializeField, Range(0f, 1f)] private float trustWeight = 1f;
        [SerializeField] private bool spoofFlagged;

        private MeshRenderer meshRenderer;
        private MaterialPropertyBlock propertyBlock;

        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");
        private static readonly int TrustId = Shader.PropertyToID("_Trust");
        private static readonly int SpoofId = Shader.PropertyToID("_Spoof");

        public float TrustWeight => trustWeight;
        public bool SpoofFlagged => spoofFlagged;

        private void Awake()
        {
            meshRenderer = GetComponent<MeshRenderer>();
            propertyBlock = new MaterialPropertyBlock();
            ApplyProperties();
        }

        private void OnValidate()
        {
            if (meshRenderer == null) meshRenderer = GetComponent<MeshRenderer>();
            propertyBlock ??= new MaterialPropertyBlock();
            ApplyProperties();
        }

        public void SetTrustWeight(float value)
        {
            trustWeight = Mathf.Clamp01(value);
            ApplyProperties();
        }

        public void SetSpoofFlag(bool value)
        {
            spoofFlagged = value;
            ApplyProperties();
        }

        private void ApplyProperties()
        {
            if (meshRenderer == null) return;
            propertyBlock.SetColor(BaseColorId, baseColor);
            propertyBlock.SetFloat(TrustId, trustWeight);
            propertyBlock.SetFloat(SpoofId, spoofFlagged ? 1f : 0f);
            meshRenderer.SetPropertyBlock(propertyBlock);
        }
    }
}
