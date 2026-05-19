namespace ChaosOne.Decisions
{
    /// <summary>
    /// The effector cost of a course of action, expressed as the delta
    /// against the current magazine state. Positive values represent
    /// rounds expended; HEL is measured in megajoules.
    /// </summary>
    public readonly struct MagazineDelta
    {
        public readonly int NextGenInterceptor;
        public readonly int Sm3;
        public readonly int Sm6;
        public readonly int Pac3;
        public readonly float HighEnergyLaserMegajoules;

        public MagazineDelta(
            int ngi = 0,
            int sm3 = 0,
            int sm6 = 0,
            int pac3 = 0,
            float helMegajoules = 0f)
        {
            NextGenInterceptor = ngi;
            Sm3 = sm3;
            Sm6 = sm6;
            Pac3 = pac3;
            HighEnergyLaserMegajoules = helMegajoules;
        }

        public bool IsNonKineticOnly =>
            NextGenInterceptor == 0 && Sm3 == 0 && Sm6 == 0 && Pac3 == 0;
    }
}
