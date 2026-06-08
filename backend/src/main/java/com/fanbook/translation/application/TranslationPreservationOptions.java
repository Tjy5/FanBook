package com.fanbook.translation.application;

public record TranslationPreservationOptions(
        boolean urls,
        boolean emails,
        boolean footnoteMarkers,
        boolean inlineMarkup,
        boolean listNumbering,
        boolean codeLikeSpans
) {
    public static TranslationPreservationOptions defaults() {
        return new TranslationPreservationOptions(true, true, true, true, true, true);
    }
}
