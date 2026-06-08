package com.fanbook.export.application;

import com.fanbook.book.application.BookAccessService;
import com.fanbook.book.application.SegmentInlineMarkup;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.domain.SegmentStatus;
import com.fanbook.book.infrastructure.BookRepository;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.common.storage.StorageService;
import com.fanbook.export.domain.ExportArtifactEntity;
import com.fanbook.export.domain.ExportArtifactKind;
import com.fanbook.export.domain.ExportArtifactStatus;
import com.fanbook.export.infrastructure.ExportArtifactRepository;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

@Service
public class ExportService {

    private final BookRepository bookRepository;
    private final SegmentRepository segmentRepository;
    private final StorageService storageService;
    private final ExportArtifactRepository artifactRepository;
    private final BookAccessService bookAccessService;

    public ExportService(
            BookRepository bookRepository,
            SegmentRepository segmentRepository,
            StorageService storageService,
            ExportArtifactRepository artifactRepository,
            BookAccessService bookAccessService
    ) {
        this.bookRepository = bookRepository;
        this.segmentRepository = segmentRepository;
        this.storageService = storageService;
        this.artifactRepository = artifactRepository;
        this.bookAccessService = bookAccessService;
    }

    @Transactional
    public ExportArtifactEntity exportZhForCurrentUser(Long bookId) {
        bookAccessService.requireAccessibleBook(bookId);
        return exportZh(bookId);
    }

    @Transactional
    public ExportArtifactEntity exportZh(Long bookId) {
        return export(bookId, ExportArtifactKind.ZH_EPUB, "zh.epub", false);
    }

    @Transactional
    public ExportArtifactEntity exportBilingualForCurrentUser(Long bookId) {
        bookAccessService.requireAccessibleBook(bookId);
        return exportBilingual(bookId);
    }

    @Transactional
    public ExportArtifactEntity exportBilingual(Long bookId) {
        return export(bookId, ExportArtifactKind.BILINGUAL_EPUB, "bilingual.epub", true);
    }

    @Transactional(readOnly = true)
    public ExportArtifactEntity requireReadyArtifactForCurrentUser(Long bookId, ExportArtifactKind kind) {
        bookAccessService.requireAccessibleBook(bookId);
        return requireReadyArtifact(bookId, kind);
    }

    @Transactional(readOnly = true)
    public ExportArtifactEntity requireReadyArtifact(Long bookId, ExportArtifactKind kind) {
        return artifactRepository.findFirstByBook_IdAndKindAndStatusOrderByCreatedAtDescIdDesc(bookId, kind, ExportArtifactStatus.READY)
                .filter(artifact -> artifact.getObjectKey() != null && storageService.exists(artifact.getObjectKey()))
                .orElseThrow(() -> new FanbookException(
                        ErrorCode.EXPORT_NOT_READY,
                        HttpStatus.CONFLICT,
                        "Export artifact '" + kind.name() + "' for book '" + bookId + "' is not ready."
                ));
    }

    private ExportArtifactEntity export(Long bookId, ExportArtifactKind kind, String filename, boolean bilingual) {
        BookEntity book = bookRepository.findById(bookId)
                .orElseThrow(() -> new FanbookException(ErrorCode.BOOK_NOT_FOUND, HttpStatus.NOT_FOUND, "Book '" + bookId + "' was not found."));
        List<SegmentEntity> segments = segmentRepository.findByBookIdOrderByChapterIdAscSegmentOrderAsc(bookId);
        if (segments.isEmpty() || segments.stream().anyMatch(segment -> segment.getStatus() != SegmentStatus.TRANSLATED
                || segment.getTranslatedText() == null
                || segment.getTranslatedText().isBlank())) {
            throw new FanbookException(ErrorCode.EXPORT_NOT_READY, HttpStatus.CONFLICT, "Book '" + bookId + "' is not fully translated.");
        }

        byte[] exported = rewriteEpub(storageService.read(book.getSourceObjectKey()), segments, bilingual);
        String objectKey = "exports/" + bookId + "/" + filename;
        storageService.put(objectKey, exported);

        ExportArtifactEntity artifact = new ExportArtifactEntity(book, kind, ExportArtifactStatus.READY, filename);
        artifact.markReady(objectKey, exported.length, sha256(exported));
        return artifactRepository.save(artifact);
    }

    private byte[] rewriteEpub(byte[] source, List<SegmentEntity> segments, boolean bilingual) {
        try {
            Map<String, List<LocatedSegment>> segmentsByDocPath = segmentsByDocPath(segments);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(source), StandardCharsets.UTF_8);
                 ZipOutputStream rewritten = new ZipOutputStream(out, StandardCharsets.UTF_8)) {
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    rewritten.putNextEntry(new ZipEntry(entry.getName()));
                    byte[] bytes = zip.readAllBytes();
                    String docPath = entry.getName().replace('\\', '/');
                    if (!entry.isDirectory() && segmentsByDocPath.containsKey(docPath)) {
                        bytes = rewriteXhtml(bytes, docPath, segmentsByDocPath.remove(docPath), bilingual);
                    }
                    rewritten.write(bytes);
                    rewritten.closeEntry();
                }
            }
            if (!segmentsByDocPath.isEmpty()) {
                throw exportFailed("Source EPUB is missing XHTML document(s): " + segmentsByDocPath.keySet());
            }
            return out.toByteArray();
        } catch (FanbookException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new FanbookException(ErrorCode.EXPORT_FAILED, HttpStatus.INTERNAL_SERVER_ERROR, exception.getMessage());
        }
    }

    private Map<String, List<LocatedSegment>> segmentsByDocPath(List<SegmentEntity> segments) {
        Map<String, List<LocatedSegment>> grouped = new HashMap<>();
        for (SegmentEntity segment : segments) {
            SegmentInlineMarkup.Locator locator = locator(segment);
            grouped.computeIfAbsent(locator.docPath(), key -> new ArrayList<>())
                    .add(new LocatedSegment(segment, locator));
        }
        grouped.values().forEach(list -> list.sort(Comparator
                .comparingInt((LocatedSegment located) -> located.locator().index())
                .thenComparingInt(located -> located.locator().partIndex() == null ? -1 : located.locator().partIndex())));
        return grouped;
    }

    private SegmentInlineMarkup.Locator locator(SegmentEntity segment) {
        try {
            SegmentInlineMarkup.Locator locator = SegmentInlineMarkup.locator(segment.getLocatorJson());
            if (locator.docPath() == null || locator.docPath().isBlank() || locator.index() == null || locator.index() < 0) {
                throw exportFailed("Invalid locator for segment '" + segment.getId() + "'.");
            }
            return locator;
        } catch (FanbookException exception) {
            throw exception;
        } catch (Exception exception) {
            throw exportFailed("Invalid locator for segment '" + segment.getId() + "'.");
        }
    }

    private byte[] rewriteXhtml(
            byte[] content,
            String docPath,
            List<LocatedSegment> locatedSegments,
            boolean bilingual
    ) {
        Document doc = xml(content, docPath);
        List<Element> elements = elements(doc);
        for (List<LocatedSegment> locatedGroup : groupByElementIndex(locatedSegments)) {
            LocatedSegment first = locatedGroup.getFirst();
            if (first.locator().index() >= elements.size()) {
                throw exportFailed("Locator index '" + first.locator().index() + "' is out of range for '" + docPath + "'.");
            }
            Element sourceElement = elements.get(first.locator().index());
            String locatedText = normalizeSegmentText(sourceElement.getTextContent());
            List<LocatedSegment> orderedParts = orderedParts(locatedGroup);
            String sourceText = normalizeSegmentText(joinSourceText(orderedParts));
            if (!locatedText.equals(sourceText)) {
                throw exportFailed("Locator mismatch for segment '" + first.segment().getId() + "' in '" + docPath + "'.");
            }
            String translatedText = joinTranslatedText(orderedParts);
            rewriteElement(doc, sourceElement, first.locator(), translatedText, bilingual, first.segment().getId());
        }
        return serialize(doc);
    }

    private static void rewriteElement(
            Document doc,
            Element sourceElement,
            SegmentInlineMarkup.Locator locator,
            String translatedText,
            boolean bilingual,
            Long segmentId
    ) {
        if (bilingual) {
            Element translatedElement = (Element) sourceElement.cloneNode(true);
            applyTranslatedText(doc, translatedElement, locator, translatedText, segmentId);
            insertAfter(sourceElement, translatedElement);
        } else {
            applyTranslatedText(doc, sourceElement, locator, translatedText, segmentId);
        }
    }

    private static void applyTranslatedText(
            Document doc,
            Element target,
            SegmentInlineMarkup.Locator locator,
            String translatedText,
            Long segmentId
    ) {
        if (!locator.hasInlinePlaceholders()) {
            target.setTextContent(translatedText);
            return;
        }
        try {
            SegmentInlineMarkup.restoreInlineChildren(doc, target, locator, translatedText);
        } catch (Exception exception) {
            throw exportFailed("Inline placeholder restoration failed for segment '" + segmentId + "': " + exception.getMessage());
        }
    }

    private static List<List<LocatedSegment>> groupByElementIndex(List<LocatedSegment> locatedSegments) {
        List<List<LocatedSegment>> groups = new ArrayList<>();
        Integer currentIndex = null;
        List<LocatedSegment> current = new ArrayList<>();
        for (LocatedSegment located : locatedSegments) {
            if (currentIndex == null || currentIndex.equals(located.locator().index())) {
                current.add(located);
                currentIndex = located.locator().index();
                continue;
            }
            groups.add(List.copyOf(current));
            current.clear();
            current.add(located);
            currentIndex = located.locator().index();
        }
        if (!current.isEmpty()) {
            groups.add(List.copyOf(current));
        }
        return groups;
    }

    private static List<LocatedSegment> orderedParts(List<LocatedSegment> locatedGroup) {
        if (locatedGroup.size() == 1
                && locatedGroup.getFirst().locator().partIndex() == null
                && locatedGroup.getFirst().locator().partCount() == null) {
            return locatedGroup;
        }
        Integer partCount = locatedGroup.getFirst().locator().partCount();
        if (partCount == null || partCount != locatedGroup.size()) {
            throw exportFailed("Invalid locator part count for segment '" + locatedGroup.getFirst().segment().getId() + "'.");
        }
        List<LocatedSegment> ordered = locatedGroup.stream()
                .sorted(Comparator.comparingInt(located -> located.locator().partIndex() == null ? -1 : located.locator().partIndex()))
                .toList();
        for (int i = 0; i < ordered.size(); i++) {
            SegmentInlineMarkup.Locator locator = ordered.get(i).locator();
            if (locator.partIndex() == null || locator.partCount() == null
                    || !locator.partCount().equals(partCount) || locator.partIndex() != i) {
                throw exportFailed("Invalid locator part order for segment '" + ordered.get(i).segment().getId() + "'.");
            }
        }
        return ordered;
    }

    private static String joinSourceText(List<LocatedSegment> locatedSegments) {
        return locatedSegments.stream()
                .map(located -> located.segment().getSourceText())
                .collect(Collectors.joining(" "));
    }

    private static String joinTranslatedText(List<LocatedSegment> locatedSegments) {
        return locatedSegments.stream()
                .map(located -> located.segment().getTranslatedText())
                .collect(Collectors.joining(" "));
    }

    private static Document xml(byte[] content, String path) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            return factory.newDocumentBuilder().parse(new ByteArrayInputStream(content));
        } catch (FanbookException exception) {
            throw exception;
        } catch (Exception exception) {
            throw exportFailed("EPUB document '" + path + "' is not well-formed XML.");
        }
    }

    private static List<Element> elements(Document doc) {
        NodeList nodes = doc.getElementsByTagNameNS("*", "*");
        List<Element> elements = new ArrayList<>(nodes.getLength());
        for (int i = 0; i < nodes.getLength(); i++) {
            elements.add((Element) nodes.item(i));
        }
        return elements;
    }

    private static void insertAfter(Node reference, Node inserted) {
        Node parent = reference.getParentNode();
        Node next = reference.getNextSibling();
        if (next == null) {
            parent.appendChild(inserted);
        } else {
            parent.insertBefore(inserted, next);
        }
    }

    private static byte[] serialize(Document doc) {
        try {
            TransformerFactory factory = TransformerFactory.newInstance();
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            var transformer = factory.newTransformer();
            transformer.setOutputProperty(OutputKeys.ENCODING, StandardCharsets.UTF_8.name());
            transformer.setOutputProperty(OutputKeys.METHOD, "xml");
            transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "no");
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            transformer.transform(new DOMSource(doc), new StreamResult(out));
            return out.toByteArray();
        } catch (Exception exception) {
            throw exportFailed("Failed to serialize rewritten EPUB XHTML.");
        }
    }

    private static String normalizeSegmentText(String text) {
        return text == null ? "" : text.trim().replaceAll("\\s+", " ");
    }

    private static FanbookException exportFailed(String message) {
        return new FanbookException(ErrorCode.EXPORT_FAILED, HttpStatus.INTERNAL_SERVER_ERROR, message);
    }

    private static String sha256(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }

    private record LocatedSegment(SegmentEntity segment, SegmentInlineMarkup.Locator locator) {
    }
}
