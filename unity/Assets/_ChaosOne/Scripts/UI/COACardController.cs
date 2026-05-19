using System;
using ChaosOne.Decisions;
using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Renders a single COA card. Holds references into the cloned UXML
    /// template, exposes Authorize / Object click events, and updates the
    /// countdown bar on each tick.
    /// </summary>
    public sealed class COACardController
    {
        public VisualElement Root { get; }
        public string CoaId { get; }
        public event Action<string> Authorized;
        public event Action<string> Objected;

        private readonly Label headlineLabel;
        private readonly Label whyLabel;
        private readonly Label leakageLabel;
        private readonly Label costLabel;
        private readonly Label escalationLabel;
        private readonly Label releasabilityLabel;
        private readonly VisualElement countdownFill;
        private readonly Label countdownLabel;
        private readonly Label recommendedBadge;
        private readonly Button authorizeButton;
        private readonly Button objectButton;

        private readonly float countdownInitialSeconds;

        public COACardController(VisualElement root, CourseOfAction coa)
        {
            Root = root;
            CoaId = coa.Id;
            countdownInitialSeconds = coa.CountdownSeconds;

            headlineLabel = root.Q<Label>("coa-headline");
            whyLabel = root.Q<Label>("coa-why");
            leakageLabel = root.Q<Label>("coa-leakage");
            costLabel = root.Q<Label>("coa-cost");
            escalationLabel = root.Q<Label>("coa-escalation");
            releasabilityLabel = root.Q<Label>("coa-releasability");
            countdownFill = root.Q<VisualElement>("countdown-fill");
            countdownLabel = root.Q<Label>("countdown-label");
            recommendedBadge = root.Q<Label>("recommended-badge");
            authorizeButton = root.Q<Button>("btn-authorize");
            objectButton = root.Q<Button>("btn-object");

            Bind(coa);
            WireButtons();
        }

        private void Bind(CourseOfAction coa)
        {
            Root.Q<Label>("coa-id").text = coa.Id;
            headlineLabel.text = coa.Headline;
            whyLabel.text = coa.WhyOneLine;

            leakageLabel.text = $"LEAKAGE {coa.ExpectedLeakage.Point:F2} ±{coa.ExpectedLeakage.BandWidth / 2f:F2}";
            costLabel.text = FormatCost(coa.Cost);
            escalationLabel.text = coa.Escalation.ToString().ToUpperInvariant();
            releasabilityLabel.text = coa.Releasability;
            countdownLabel.text = $"{coa.CountdownSeconds:F0}s";

            if (coa.IsRecommended)
            {
                recommendedBadge.style.display = DisplayStyle.Flex;
                Root.AddToClassList("coa-card--recommended");
            }
            else
            {
                recommendedBadge.style.display = DisplayStyle.None;
            }
        }

        private void WireButtons()
        {
            authorizeButton.clicked += () => Authorized?.Invoke(CoaId);
            objectButton.clicked += () => Objected?.Invoke(CoaId);
        }

        public void UpdateCountdown(float secondsRemaining)
        {
            var fraction = countdownInitialSeconds > 0f
                ? UnityEngine.Mathf.Clamp01(secondsRemaining / countdownInitialSeconds)
                : 0f;
            if (countdownFill != null) countdownFill.style.width = Length.Percent(fraction * 100f);
            if (countdownLabel != null) countdownLabel.text = $"{secondsRemaining:F0}s";

            if (fraction < 0.25f)
            {
                Root.AddToClassList("coa-card--countdown-low");
            }
            else
            {
                Root.RemoveFromClassList("coa-card--countdown-low");
            }
        }

        private static string FormatCost(MagazineDelta cost)
        {
            var parts = new System.Collections.Generic.List<string>();
            if (cost.NextGenInterceptor > 0) parts.Add($"{cost.NextGenInterceptor} NGI");
            if (cost.Sm3 > 0) parts.Add($"{cost.Sm3} SM-3");
            if (cost.Sm6 > 0) parts.Add($"{cost.Sm6} SM-6");
            if (cost.Pac3 > 0) parts.Add($"{cost.Pac3} PAC-3");
            if (cost.HighEnergyLaserMegajoules > 0f) parts.Add($"HEL {cost.HighEnergyLaserMegajoules:F1}MJ");
            return parts.Count == 0 ? "COST NIL" : "COST " + string.Join(" / ", parts);
        }
    }
}
