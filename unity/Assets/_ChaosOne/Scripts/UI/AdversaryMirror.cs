using System.Collections.Generic;
using ChaosOne.Core;
using ChaosOne.Decisions;
using UnityEngine;
using UnityEngine.UIElements;

namespace ChaosOne.UI
{
    /// <summary>
    /// Renders the current adversary playbook distribution and a rolling
    /// cost-imposition sparkline. Up to three hypothesis rows visible.
    /// </summary>
    [RequireComponent(typeof(UIDocument))]
    public sealed class AdversaryMirror : MonoBehaviour
    {
        [SerializeField] private int hypothesesToShow = 3;

        private VisualElement root;
        private VisualElement hypothesisStack;
        private VisualElement sparkline;
        private Label costIndexLabel;

        private readonly List<VisualElement> hypothesisRows = new();

        private void OnEnable()
        {
            var document = GetComponent<UIDocument>();
            UIDocumentLayout.FillPanel(document);
            var rv = document.rootVisualElement;
            if (rv == null) { enabled = false; return; }

            root = rv.Q<VisualElement>("adversary-mirror");
            hypothesisStack = rv.Q<VisualElement>("hypothesis-stack");
            sparkline = rv.Q<VisualElement>("sparkline");
            costIndexLabel = rv.Q<Label>("cost-index");

            BuildHypothesisRows();

            EventBus.Subscribe<AdversaryPlaybookUpdated>(OnPlaybookUpdated);
        }

        private void OnDisable()
        {
            EventBus.Unsubscribe<AdversaryPlaybookUpdated>(OnPlaybookUpdated);
        }

        private void BuildHypothesisRows()
        {
            if (hypothesisStack == null) return;
            hypothesisStack.Clear();
            hypothesisRows.Clear();

            for (var i = 0; i < hypothesesToShow; i++)
            {
                var row = new VisualElement();
                row.AddToClassList("hypothesis-row");

                var weightLabel = new Label("--%");
                weightLabel.AddToClassList("hypothesis-row__weight");
                weightLabel.name = "weight";

                var nameLabel = new Label("(empty)");
                nameLabel.AddToClassList("hypothesis-row__name");
                nameLabel.name = "name";

                var delta = new Label("");
                delta.AddToClassList("hypothesis-row__delta");
                delta.name = "delta";

                var bar = new VisualElement();
                bar.AddToClassList("hypothesis-row__bar");
                var fill = new VisualElement();
                fill.AddToClassList("hypothesis-row__bar-fill");
                fill.name = "fill";
                bar.Add(fill);

                row.Add(weightLabel);
                row.Add(nameLabel);
                row.Add(delta);
                row.Add(bar);

                hypothesisStack.Add(row);
                hypothesisRows.Add(row);
            }
        }

        private void OnPlaybookUpdated(AdversaryPlaybookUpdated evt)
        {
            RenderHypotheses(evt.Distribution);
            RenderCostImposition(evt.Distribution.CostImpositionIndex);
            RenderSparkline();
        }

        private void RenderHypotheses(AdversaryDistribution distribution)
        {
            for (var i = 0; i < hypothesisRows.Count; i++)
            {
                var row = hypothesisRows[i];

                if (i >= distribution.Hypotheses.Count)
                {
                    row.style.display = DisplayStyle.None;
                    continue;
                }

                var hypothesis = distribution.Hypotheses[i];
                row.style.display = DisplayStyle.Flex;
                row.Q<Label>("weight").text = $"{Mathf.RoundToInt(hypothesis.Weight * 100f)}%";
                row.Q<Label>("name").text = hypothesis.DisplayName;
                row.Q<Label>("delta").text = FormatDelta(hypothesis.Delta30s);
                var fill = row.Q<VisualElement>("fill");
                if (fill != null) fill.style.width = Length.Percent(Mathf.Clamp01(hypothesis.Weight) * 100f);
            }
        }

        private void RenderCostImposition(float index)
        {
            if (costIndexLabel == null) return;
            var pctDelta = (index - 1.0f) * 100f;
            var sign = pctDelta >= 0f ? "+" : "";
            costIndexLabel.text = $"COST IMPOSITION {sign}{pctDelta:F0}% ADV";
        }

        private void RenderSparkline()
        {
            if (sparkline == null) return;
            if (!ServiceRegistry.TryResolve<AdversaryMirrorService>(out var service)) return;

            sparkline.Clear();
            var history = service.CostImpositionHistory;
            if (history.Count == 0) return;

            var minValue = float.MaxValue;
            var maxValue = float.MinValue;
            foreach (var sample in history)
            {
                if (sample < minValue) minValue = sample;
                if (sample > maxValue) maxValue = sample;
            }

            var range = Mathf.Max(0.05f, maxValue - minValue);

            foreach (var sample in history)
            {
                var normalized = (sample - minValue) / range;
                var bar = new VisualElement();
                bar.AddToClassList("sparkline__bar");
                bar.style.height = Length.Percent(Mathf.Lerp(15f, 100f, normalized));
                sparkline.Add(bar);
            }
        }

        private static string FormatDelta(float delta)
        {
            if (Mathf.Abs(delta) < 0.005f) return "→";
            return delta > 0f ? "↑" : "↓";
        }
    }
}
