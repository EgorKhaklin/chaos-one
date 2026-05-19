namespace ChaosOne.Decisions
{
    /// <summary>
    /// An immutable course-of-action proposal. The DecisionsPanel renders one
    /// card per active COA; the COAQueue advances countdowns and decides when
    /// auto-authorization fires under the active ROE envelope.
    /// </summary>
    public sealed class CourseOfAction
    {
        public string Id { get; }
        public string Headline { get; }
        public string WhyOneLine { get; }
        public OutcomeBand ExpectedLeakage { get; }
        public MagazineDelta Cost { get; }
        public EscalationLevel Escalation { get; }
        public string Releasability { get; }
        public float CountdownSeconds { get; }
        public bool IsRecommended { get; }

        public CourseOfAction(
            string id,
            string headline,
            string whyOneLine,
            OutcomeBand expectedLeakage,
            MagazineDelta cost,
            EscalationLevel escalation,
            string releasability,
            float countdownSeconds,
            bool isRecommended)
        {
            Id = id;
            Headline = headline;
            WhyOneLine = whyOneLine;
            ExpectedLeakage = expectedLeakage;
            Cost = cost;
            Escalation = escalation;
            Releasability = releasability;
            CountdownSeconds = countdownSeconds;
            IsRecommended = isRecommended;
        }
    }
}
