namespace ChaosOne.Decisions
{
    /// <summary>
    /// A predicted outcome with its uncertainty band (low / point / high).
    /// Renders as a band-and-whisker mark, never as a bare point estimate.
    /// </summary>
    public readonly struct OutcomeBand
    {
        public readonly float Point;
        public readonly float Low;
        public readonly float High;

        public OutcomeBand(float point, float low, float high)
        {
            Point = point;
            Low = low;
            High = high;
        }

        public float BandWidth => High - Low;

        public override string ToString() => $"{Point:F2} (±{(High - Low) / 2f:F2})";
    }
}
