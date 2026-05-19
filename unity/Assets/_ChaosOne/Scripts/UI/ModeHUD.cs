using ChaosOne.Core;
using ChaosOne.Decisions;
using UnityEngine;
using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Top-anchored persistent strip. Single line of state the operator
    /// glances at without looking: mode letter, mode label, ROE envelope,
    /// comms health, crypto posture, magazine summary.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class ModeHUD : MonoBehaviour
    {
        [SerializeField] private string roeEnvelopeId = "ROE-2";
        [SerializeField] private int commsHealthPercent = 98;
        [SerializeField] private string cryptoPosture = "PQC-HYBRID";
        [SerializeField] private string magazineSummary = "MAG 22 NGI / 48 SM-3 / 320 PAC-3 / HEL 1.2MJ";

        private VisualElement root;
        private Label modeLetterLabel;
        private Label modeNameLabel;
        private Label roeLabel;
        private Label commsLabel;
        private Label cryptoLabel;
        private Label magazineLabel;

        private static readonly string AmberClass = "mode-hud--amber";
        private static readonly string RedClass = "mode-hud--red";

        private void OnEnable()
        {
            var document = GetComponent<UIDocument>();
            var rv = document.rootVisualElement;
            if (rv == null) { enabled = false; return; }

            root = rv.Q<VisualElement>("mode-hud");
            modeLetterLabel = rv.Q<Label>("mode-letter");
            modeNameLabel = rv.Q<Label>("mode-name");
            roeLabel = rv.Q<Label>("roe");
            commsLabel = rv.Q<Label>("comms");
            cryptoLabel = rv.Q<Label>("crypto");
            magazineLabel = rv.Q<Label>("magazine");

            EventBus.Subscribe<ModeChanged>(OnModeChanged);
            EventBus.Subscribe<ROEEnvelopeChanged>(OnRoeChanged);

            Render(OperationalMode.Nominal);
        }

        private void OnDisable()
        {
            EventBus.Unsubscribe<ModeChanged>(OnModeChanged);
            EventBus.Unsubscribe<ROEEnvelopeChanged>(OnRoeChanged);
        }

        private void OnModeChanged(ModeChanged evt) => Render(evt.Current);

        private void OnRoeChanged(ROEEnvelopeChanged evt)
        {
            roeEnvelopeId = evt.CurrentId;
            if (roeLabel != null) roeLabel.text = roeEnvelopeId;
        }

        private void Render(OperationalMode mode)
        {
            if (root == null) return;

            root.RemoveFromClassList(AmberClass);
            root.RemoveFromClassList(RedClass);

            (string letter, string name, string toneClass) = mode switch
            {
                OperationalMode.Nominal => ("A", "NOMINAL", null),
                OperationalMode.SensorDegraded => ("B", "SENSOR DEGRADED", AmberClass),
                OperationalMode.CommsDegraded => ("C", "COMMS DEGRADED", AmberClass),
                OperationalMode.CyberSuspect => ("D", "CYBER-SUSPECT", RedClass),
                OperationalMode.AdvisoryOnly => ("E", "ADVISORY ONLY", AmberClass),
                OperationalMode.PrePositionedAutonomous => ("F", "AUTONOMOUS FIRE", RedClass),
                _ => ("?", "UNKNOWN", AmberClass),
            };

            if (modeLetterLabel != null) modeLetterLabel.text = letter;
            if (modeNameLabel != null) modeNameLabel.text = name;
            if (roeLabel != null) roeLabel.text = roeEnvelopeId;
            if (commsLabel != null) commsLabel.text = $"COMMS {commsHealthPercent}%";
            if (cryptoLabel != null) cryptoLabel.text = cryptoPosture;
            if (magazineLabel != null) magazineLabel.text = magazineSummary;

            if (toneClass != null) root.AddToClassList(toneClass);
        }
    }
}
