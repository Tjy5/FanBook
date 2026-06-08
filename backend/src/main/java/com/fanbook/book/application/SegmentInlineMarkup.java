package com.fanbook.book.application;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.book.domain.SegmentEntity;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;

public final class SegmentInlineMarkup {

    private static final ObjectMapper OBJECT_MAPPER = JsonMapper.builder()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .serializationInclusion(JsonInclude.Include.NON_EMPTY)
            .build();
    private static final Pattern PLACEHOLDER = Pattern.compile("\\[id\\d+\\]");
    private static final Set<String> SUPPORTED_INLINE_TAGS = Set.of(
            "a",
            "abbr",
            "b",
            "cite",
            "code",
            "em",
            "i",
            "kbd",
            "mark",
            "q",
            "s",
            "small",
            "span",
            "strong",
            "sub",
            "sup",
            "u",
            "var"
    );

    private SegmentInlineMarkup() {
    }

    public static String locatorJson(String docPath, int index) {
        return locatorJson(new Locator(docPath, index, null, null, null, List.of()));
    }

    public static String locatorJson(String docPath, int index, int partIndex, int partCount) {
        return locatorJson(new Locator(docPath, index, partIndex, partCount, null, List.of()));
    }

    public static String locatorJson(String docPath, int index, InlinePlan plan) {
        return locatorJson(new Locator(docPath, index, null, null, plan.sourceTemplate(), plan.placeholders()));
    }

    public static String locatorJson(Locator locator) {
        try {
            return OBJECT_MAPPER.writeValueAsString(locator);
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to serialize EPUB segment locator.", exception);
        }
    }

    public static Locator locator(String locatorJson) {
        try {
            return OBJECT_MAPPER.readValue(locatorJson, Locator.class);
        } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid EPUB segment locator JSON.", exception);
        }
    }

    public static Optional<Locator> tryLocator(String locatorJson) {
        try {
            return Optional.of(locator(locatorJson));
        } catch (Exception exception) {
            return Optional.empty();
        }
    }

    public static String providerSourceText(SegmentEntity segment) {
        return tryLocator(segment.getLocatorJson())
                .filter(Locator::hasInlinePlaceholders)
                .map(Locator::sourceTemplate)
                .filter(template -> template != null && !template.isBlank())
                .orElse(segment.getSourceText());
    }

    public static String displayTranslatedText(SegmentEntity segment) {
        return displayText(segment.getTranslatedText(), segment.getLocatorJson());
    }

    public static String displayText(String text, String locatorJson) {
        if (text == null) {
            return null;
        }
        return tryLocator(locatorJson)
                .filter(Locator::hasInlinePlaceholders)
                .map(locator -> stripKnownPlaceholders(text, locator))
                .orElse(text);
    }

    public static PlaceholderValidation validateTranslatedText(String translatedText, String locatorJson) {
        Optional<Locator> locator = tryLocator(locatorJson);
        if (locator.isEmpty() || !locator.get().hasInlinePlaceholders()) {
            return PlaceholderValidation.ok();
        }
        return validatePlaceholders(translatedText, locator.get());
    }

    public static void restoreInlineChildren(Document document, Element target, Locator locator, String translatedText) {
        PlaceholderValidation validation = validatePlaceholders(translatedText, locator);
        if (!validation.valid()) {
            throw new IllegalArgumentException(validation.message());
        }
        List<Node> restored = restoredNodes(document, locator, translatedText);
        while (target.hasChildNodes()) {
            target.removeChild(target.getFirstChild());
        }
        for (Node node : restored) {
            target.appendChild(node);
        }
    }

    public static Optional<InlinePlan> inlinePlan(Element element, String normalizedSourceText) {
        if (!hasInlineElementChild(element)) {
            return Optional.empty();
        }
        InlinePlanBuilder builder = new InlinePlanBuilder();
        if (!appendInlineContent(element, builder)) {
            return Optional.empty();
        }
        if (builder.placeholders.isEmpty()) {
            return Optional.empty();
        }
        String sourceTemplate = normalizeTemplate(builder.text.toString());
        String plainText = stripPlaceholderTokens(sourceTemplate);
        if (!normalizeSegmentText(plainText).equals(normalizedSourceText)) {
            return Optional.empty();
        }
        return Optional.of(new InlinePlan(sourceTemplate, builder.placeholders));
    }

    public static String stripKnownPlaceholders(String text, Locator locator) {
        if (text == null || locator == null || !locator.hasInlinePlaceholders()) {
            return text;
        }
        String cleaned = text;
        for (InlinePlaceholder placeholder : locator.inlinePlaceholders()) {
            cleaned = cleaned.replace(placeholder.token(), "");
        }
        return normalizeSegmentText(cleaned);
    }

    public static String stripPlaceholderTokens(String text) {
        if (text == null) {
            return "";
        }
        return normalizeSegmentText(PLACEHOLDER.matcher(text).replaceAll(""));
    }

    public static String normalizeSegmentText(String text) {
        return text == null ? "" : text.trim().replaceAll("\\s+", " ");
    }

    private static PlaceholderValidation validatePlaceholders(String translatedText, Locator locator) {
        if (translatedText == null || translatedText.isBlank()) {
            return PlaceholderValidation.invalid("missing all inline placeholders");
        }
        List<String> expected = locator.tokensInOrder();
        List<String> actual = placeholderTokens(translatedText);
        Set<String> expectedSet = new HashSet<>(expected);
        List<String> extra = actual.stream()
                .filter(token -> !expectedSet.contains(token))
                .distinct()
                .toList();
        if (!extra.isEmpty()) {
            return PlaceholderValidation.invalid("extra inline placeholder(s): " + String.join(", ", extra));
        }
        List<String> missing = expected.stream()
                .filter(token -> !actual.contains(token))
                .toList();
        if (!missing.isEmpty()) {
            return PlaceholderValidation.invalid("missing inline placeholder(s): " + String.join(", ", missing));
        }
        List<String> duplicated = actual.stream()
                .filter(token -> Collections.frequency(actual, token) > 1)
                .distinct()
                .toList();
        if (!duplicated.isEmpty()) {
            return PlaceholderValidation.invalid("duplicate inline placeholder(s): " + String.join(", ", duplicated));
        }
        if (!actual.equals(expected)) {
            return PlaceholderValidation.invalid("inline placeholders are out of order");
        }
        return PlaceholderValidation.ok();
    }

    private static List<String> placeholderTokens(String text) {
        var matcher = PLACEHOLDER.matcher(text);
        List<String> tokens = new ArrayList<>();
        while (matcher.find()) {
            tokens.add(matcher.group());
        }
        return tokens;
    }

    private static List<Node> restoredNodes(Document document, Locator locator, String translatedText) {
        Map<String, InlinePlaceholder> byToken = new LinkedHashMap<>();
        locator.inlinePlaceholders().forEach(placeholder -> byToken.put(placeholder.token(), placeholder));
        List<Node> roots = new ArrayList<>();
        List<OpenFrame> stack = new ArrayList<>();
        int cursor = 0;
        var matcher = PLACEHOLDER.matcher(translatedText);
        while (matcher.find()) {
            appendText(document, roots, stack, translatedText.substring(cursor, matcher.start()));
            InlinePlaceholder placeholder = byToken.get(matcher.group());
            if (placeholder == null) {
                throw new IllegalArgumentException("unknown inline placeholder " + matcher.group());
            }
            if (InlinePlaceholderKind.OPEN.name().equals(placeholder.kind())) {
                Element element = createInlineElement(document, placeholder);
                appendNode(roots, stack, element);
                stack.add(new OpenFrame(placeholder.token(), placeholder.closeToken(), element));
            } else if (InlinePlaceholderKind.CLOSE.name().equals(placeholder.kind())) {
                if (stack.isEmpty() || !matcher.group().equals(stack.getLast().closeToken())) {
                    throw new IllegalArgumentException("inline placeholder nesting is invalid");
                }
                stack.removeLast();
            } else {
                throw new IllegalArgumentException("unsupported inline placeholder kind " + placeholder.kind());
            }
            cursor = matcher.end();
        }
        appendText(document, roots, stack, translatedText.substring(cursor));
        if (!stack.isEmpty()) {
            throw new IllegalArgumentException("unclosed inline placeholder " + stack.getLast().openToken());
        }
        return roots;
    }

    private static void appendText(Document document, List<Node> roots, List<OpenFrame> stack, String text) {
        if (text == null || text.isEmpty()) {
            return;
        }
        appendNode(roots, stack, document.createTextNode(text));
    }

    private static void appendNode(List<Node> roots, List<OpenFrame> stack, Node node) {
        if (stack.isEmpty()) {
            roots.add(node);
        } else {
            stack.getLast().element().appendChild(node);
        }
    }

    private static Element createInlineElement(Document document, InlinePlaceholder placeholder) {
        String namespaceUri = placeholder.namespaceUri();
        String tagName = placeholder.tagName();
        if (tagName == null || tagName.isBlank()) {
            throw new IllegalArgumentException("inline placeholder has no tag name");
        }
        Element element = namespaceUri == null || namespaceUri.isBlank()
                ? document.createElement(tagName)
                : document.createElementNS(namespaceUri, tagName);
        placeholder.attributes().forEach(element::setAttribute);
        return element;
    }

    private static boolean hasInlineElementChild(Element element) {
        Node child = element.getFirstChild();
        while (child != null) {
            if (child instanceof Element) {
                return true;
            }
            child = child.getNextSibling();
        }
        return false;
    }

    private static boolean appendInlineContent(Node node, InlinePlanBuilder builder) {
        Node child = node.getFirstChild();
        while (child != null) {
            if (child.getNodeType() == Node.TEXT_NODE || child.getNodeType() == Node.CDATA_SECTION_NODE) {
                builder.text.append(child.getTextContent().replaceAll("\\s+", " "));
            } else if (child instanceof Element element) {
                String tagName = element.getLocalName() == null ? element.getTagName() : element.getLocalName();
                if (!SUPPORTED_INLINE_TAGS.contains(tagName.toLowerCase(Locale.ROOT))) {
                    return false;
                }
                String openToken = builder.nextToken();
                String closeToken = builder.nextToken();
                builder.placeholders.add(new InlinePlaceholder(
                        openToken,
                        InlinePlaceholderKind.OPEN.name(),
                        tagName,
                        element.getNamespaceURI(),
                        attributes(element),
                        null,
                        closeToken
                ));
                builder.text.append(openToken);
                if (!appendInlineContent(element, builder)) {
                    return false;
                }
                builder.text.append(closeToken);
                builder.placeholders.add(new InlinePlaceholder(
                        closeToken,
                        InlinePlaceholderKind.CLOSE.name(),
                        null,
                        null,
                        Map.of(),
                        openToken,
                        null
                ));
            }
            child = child.getNextSibling();
        }
        return true;
    }

    private static Map<String, String> attributes(Element element) {
        NamedNodeMap attributes = element.getAttributes();
        if (attributes == null || attributes.getLength() == 0) {
            return Map.of();
        }
        Map<String, String> result = new LinkedHashMap<>();
        for (int i = 0; i < attributes.getLength(); i++) {
            Node attribute = attributes.item(i);
            String name = attribute.getNodeName();
            if (name == null || name.isBlank() || name.startsWith("xmlns")) {
                continue;
            }
            result.put(name, attribute.getNodeValue());
        }
        return result;
    }

    private static String normalizeTemplate(String template) {
        return template == null ? "" : template.trim().replaceAll("\\s+", " ");
    }

    private static final class InlinePlanBuilder {
        private final StringBuilder text = new StringBuilder();
        private final List<InlinePlaceholder> placeholders = new ArrayList<>();
        private int tokenIndex;

        private String nextToken() {
            return "[id" + tokenIndex++ + "]";
        }
    }

    public enum InlinePlaceholderKind {
        OPEN,
        CLOSE
    }

    public record Locator(
            String docPath,
            Integer index,
            Integer partIndex,
            Integer partCount,
            String sourceTemplate,
            List<InlinePlaceholder> inlinePlaceholders
    ) {
        public Locator {
            inlinePlaceholders = inlinePlaceholders == null ? List.of() : List.copyOf(inlinePlaceholders);
        }

        @JsonIgnore
        public boolean hasInlinePlaceholders() {
            return sourceTemplate != null && !sourceTemplate.isBlank() && !inlinePlaceholders.isEmpty();
        }

        @JsonIgnore
        public List<String> tokensInOrder() {
            return inlinePlaceholders.stream()
                    .map(InlinePlaceholder::token)
                    .toList();
        }
    }

    public record InlinePlaceholder(
            String token,
            String kind,
            String tagName,
            String namespaceUri,
            Map<String, String> attributes,
            String openToken,
            String closeToken
    ) {
        public InlinePlaceholder {
            attributes = attributes == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(attributes));
        }
    }

    public record InlinePlan(String sourceTemplate, List<InlinePlaceholder> placeholders) {
        public InlinePlan {
            placeholders = placeholders == null ? List.of() : List.copyOf(placeholders);
        }
    }

    public record PlaceholderValidation(boolean valid, String message) {
        private static PlaceholderValidation ok() {
            return new PlaceholderValidation(true, "");
        }

        private static PlaceholderValidation invalid(String message) {
            return new PlaceholderValidation(false, message);
        }
    }

    private record OpenFrame(String openToken, String closeToken, Element element) {
    }
}
