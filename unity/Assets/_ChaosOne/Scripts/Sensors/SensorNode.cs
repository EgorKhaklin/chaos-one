using UnityEngine;

namespace ChaosOne.Sensors
{
    public enum SensorDomain
    {
        Space,
        Airborne,
        Surface,
        Subsurface,
        Cyber,
    }

    /// <summary>
    /// A scene-resident sensor with a name, domain, coverage volume, and
    /// a current trust weight that the fusion layer can degrade or restore.
    /// </summary>
    public sealed class SensorNode : MonoBehaviour
    {
        [SerializeField] private string sensorId = "SENSOR";
        [SerializeField] private string displayName = "HBTSS-class";
        [SerializeField] private SensorDomain domain = SensorDomain.Space;
        [SerializeField] private CoverageVolume coverageVolume;
        [SerializeField, Range(0f, 1f)] private float trustWeight = 1f;
        [SerializeField] private bool active = true;

        public string SensorId => sensorId;
        public string DisplayName => displayName;
        public SensorDomain Domain => domain;
        public float TrustWeight => trustWeight;
        public bool Active => active;

        private void Start()
        {
            PushToCoverage();
        }

        public void SetTrustWeight(float value)
        {
            trustWeight = Mathf.Clamp01(value);
            PushToCoverage();
        }

        public void SetSpoofFlag(bool flagged)
        {
            if (coverageVolume != null) coverageVolume.SetSpoofFlag(flagged);
        }

        public void SetActive(bool value)
        {
            active = value;
            if (coverageVolume != null) coverageVolume.gameObject.SetActive(value);
        }

        private void PushToCoverage()
        {
            if (coverageVolume != null) coverageVolume.SetTrustWeight(trustWeight);
        }
    }
}
