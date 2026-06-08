package com.fanbook.testsupport;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class MinimalEpubFactory {

    private MinimalEpubFactory() {
    }

    public static byte[] create() {
        return create("""
                <h1>Chapter One</h1>
                <p>Hello world.</p>
                <p>Alice went to Wonderland.</p>
                """);
    }

    public static byte[] create(String bodyContent) {
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            try (ZipOutputStream zip = new ZipOutputStream(out, StandardCharsets.UTF_8)) {
                entry(zip, "META-INF/container.xml", """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                          <rootfiles>
                            <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
                          </rootfiles>
                        </container>
                        """);
                entry(zip, "OEBPS/content.opf", """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <package version="3.0" xmlns="http://www.idpf.org/2007/opf">
                          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                            <dc:title>Demo Book</dc:title>
                          </metadata>
                          <manifest>
                            <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
                          </manifest>
                          <spine>
                            <itemref idref="chapter1"/>
                          </spine>
                        </package>
                        """);
                entry(zip, "OEBPS/chapter1.xhtml", """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <html xmlns="http://www.w3.org/1999/xhtml">
                          <head><title>Chapter One</title></head>
                          <body>
                            %s
                          </body>
                        </html>
                        """.formatted(bodyContent));
            }
            return out.toByteArray();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    private static void entry(ZipOutputStream zip, String name, String content) throws IOException {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(content.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }
}
