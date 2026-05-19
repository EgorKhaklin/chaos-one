using ChaosOne.Core;

namespace ChaosOne.Decisions
{
    public readonly record struct AdversaryPlaybookUpdated(AdversaryDistribution Distribution) : IChaosEvent;

    public readonly record struct CostImpositionSampled(double TimestampSeconds, float Index) : IChaosEvent;
}
