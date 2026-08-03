package io.apex.standalone;

/** Shared engine boot state between the foreground service and MainActivity. */
public final class EngineState {
    public enum Phase {
        IDLE,
        STARTING,
        LOADING_PYTHON,
        LOADING_APEX,
        LISTENING,
        FAILED
    }

    private static volatile Phase phase = Phase.IDLE;
    private static volatile String detail = "";
    private static volatile String error = "";

    private EngineState() {}

    public static Phase getPhase() {
        return phase;
    }

    public static String getDetail() {
        return detail;
    }

    public static String getError() {
        return error;
    }

    public static void set(Phase newPhase, String newDetail) {
        phase = newPhase;
        detail = newDetail == null ? "" : newDetail;
        if (newPhase != Phase.FAILED) {
            error = "";
        }
    }

    public static void fail(String message) {
        phase = Phase.FAILED;
        error = message == null ? "Engine failed" : message;
        detail = error;
    }
}
