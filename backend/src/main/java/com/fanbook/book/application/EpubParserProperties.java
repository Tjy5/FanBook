package com.fanbook.book.application;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.unit.DataSize;

@ConfigurationProperties(prefix = "fanbook.epub")
public record EpubParserProperties(
        int maxEntries,
        DataSize maxExpandedSize,
        DataSize maxEntrySize
) {
    public EpubParserProperties {
        if (maxEntries <= 0) {
            maxEntries = 1_000;
        }
        if (maxExpandedSize == null) {
            maxExpandedSize = DataSize.ofMegabytes(100);
        }
        if (maxEntrySize == null) {
            maxEntrySize = DataSize.ofMegabytes(25);
        }
    }
}
