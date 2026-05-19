using ChaosOne.Core;

namespace ChaosOne.Decisions
{
    public readonly record struct COAProposed(CourseOfAction Coa) : IChaosEvent;

    public readonly record struct COACountdownTick(string CoaId, float SecondsRemaining) : IChaosEvent;

    public readonly record struct COAAuthorized(CourseOfAction Coa, AuthorizationSource Source) : IChaosEvent;

    public readonly record struct COAObjected(CourseOfAction Coa, string Reason) : IChaosEvent;

    public readonly record struct COAExpired(CourseOfAction Coa) : IChaosEvent;

    public readonly record struct ROEEnvelopeChanged(string PreviousId, string CurrentId) : IChaosEvent;
}
