using ChaosOne.Threats;

namespace ChaosOne.Core
{
    public readonly record struct TrackSpawned(ThreatTrack Track) : IChaosEvent;

    public readonly record struct TrackUpdated(ThreatTrack Track, KinematicSample Sample) : IChaosEvent;

    public readonly record struct TrackStateChanged(
        ThreatTrack Track,
        TrackState Previous,
        TrackState Current
    ) : IChaosEvent;

    public readonly record struct TrackSelected(ThreatTrack Track) : IChaosEvent;

    public readonly record struct TrackDeselected(ThreatTrack Track) : IChaosEvent;

    public readonly record struct TrackDestroyed(ThreatTrack Track) : IChaosEvent;

    public readonly record struct ModeChanged(OperationalMode Previous, OperationalMode Current) : IChaosEvent;

    public enum OperationalMode
    {
        Nominal,
        SensorDegraded,
        CommsDegraded,
        CyberSuspect,
        AdvisoryOnly,
        PrePositionedAutonomous,
    }
}
