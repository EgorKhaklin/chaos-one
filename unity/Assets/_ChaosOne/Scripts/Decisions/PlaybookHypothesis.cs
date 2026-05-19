using System.Collections.Generic;

namespace ChaosOne.Decisions
{
    /// <summary>
    /// A single hypothesis about the adversary's current playbook, plus the
    /// 30-second delta on its weight. Surfaces as one row in the Adversary
    /// Mirror.
    /// </summary>
    public readonly struct PlaybookHypothesis
    {
        public readonly string PlaybookId;
        public readonly string DisplayName;
        public readonly float Weight;
        public readonly float Delta30s;

        public PlaybookHypothesis(string playbookId, string displayName, float weight, float delta30s)
        {
            PlaybookId = playbookId;
            DisplayName = displayName;
            Weight = weight;
            Delta30s = delta30s;
        }
    }

    /// <summary>
    /// A snapshot of the adversary-model service's current state. The cost
    /// imposition index is a rolling-window economic indicator: how many
    /// dollars the adversary is spending per leaker achieved.
    /// </summary>
    public sealed class AdversaryDistribution
    {
        public double TimestampSeconds { get; }
        public IReadOnlyList<PlaybookHypothesis> Hypotheses { get; }
        public float CostImpositionIndex { get; }

        public AdversaryDistribution(
            double timestampSeconds,
            IReadOnlyList<PlaybookHypothesis> hypotheses,
            float costImpositionIndex)
        {
            TimestampSeconds = timestampSeconds;
            Hypotheses = hypotheses;
            CostImpositionIndex = costImpositionIndex;
        }
    }
}
