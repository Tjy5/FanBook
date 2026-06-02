package com.fanbook.book.api;

import com.fasterxml.jackson.annotation.JsonProperty;

public record TranslatedTitleRequest(@JsonProperty("translated_title") String translatedTitle) {
}
