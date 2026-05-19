using UnityEngine;

namespace ChaosOne.Decisions
{
    /// <summary>
    /// A named bundle of pre-authorized engagement rules. The operator selects
    /// an envelope at mission start; the COAQueue uses it to decide whether
    /// expiring countdowns auto-authorize the recommended COA.
    /// </summary>
    [CreateAssetMenu(menuName = "ChaosOne/ROE Envelope", fileName = "ROEEnvelope", order = 200)]
    public sealed class ROEEnvelope : ScriptableObject
    {
        [SerializeField] private string envelopeId = "ROE-2";
        [SerializeField] private string displayName = "Standard Defensive";
        [SerializeField, TextArea(2, 6)] private string description;

        [Header("Auto-Authorization")]
        [SerializeField] private bool autoAuthorizeOnCountdownExpiry = true;
        [SerializeField] private EscalationLevel maxEscalationForAuto = EscalationLevel.Moderate;
        [SerializeField] private bool autoAuthorizeKineticAgainstSwarms = true;
        [SerializeField] private bool autoAuthorizeDirectedEnergyTerminal = true;
        [SerializeField] private bool autoAuthorizeCyber;

        public string EnvelopeId => envelopeId;
        public string DisplayName => displayName;
        public string Description => description;
        public bool AutoAuthorizeOnCountdownExpiry => autoAuthorizeOnCountdownExpiry;
        public EscalationLevel MaxEscalationForAuto => maxEscalationForAuto;
        public bool AutoAuthorizeKineticAgainstSwarms => autoAuthorizeKineticAgainstSwarms;
        public bool AutoAuthorizeDirectedEnergyTerminal => autoAuthorizeDirectedEnergyTerminal;
        public bool AutoAuthorizeCyber => autoAuthorizeCyber;

        public bool PermitsAutoAuthorize(CourseOfAction coa)
        {
            if (!autoAuthorizeOnCountdownExpiry) return false;
            return coa.Escalation <= maxEscalationForAuto;
        }
    }
}
