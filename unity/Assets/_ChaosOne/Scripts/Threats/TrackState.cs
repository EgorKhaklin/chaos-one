namespace ChaosOne.Threats
{
    /// <summary>
    /// Discrimination state of a track. Drives envelope visuals and panel affordances.
    /// </summary>
    public enum TrackState
    {
        Acquiring,
        ConfidentRV,
        CandidateDecoy,
        EnsembleDisagreement,
        Engaged,
        Lost,
    }
}
