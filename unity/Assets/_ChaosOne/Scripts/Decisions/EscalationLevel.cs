namespace ChaosOne.Decisions
{
    public enum EscalationLevel
    {
        Low,
        Moderate,
        Elevated,
        High,
        Strategic,
    }

    public enum AuthorizationSource
    {
        Operator,
        OperatorWithCoSign,
        AutoExpire,
        AutoAuthorizedByROE,
    }
}
