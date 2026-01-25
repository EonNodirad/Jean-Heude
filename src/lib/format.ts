import markdownit from 'markdown-it';
import DOMPurify from 'isomorphic-dompurify';
import hljs from 'highlight.js';
function escapeHtml(unsafe: string) {
    return unsafe
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
const md = markdownit({
    html: false,
    linkify: true,
    typographer: true,
    highlight(str, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return `<pre class="highlight" data-language="${lang.toUpperCase()}"><code>${hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
                    }</code></pre>`;
            } catch (__) { }
        }

        return `<pre class="highlight"><code>${escapeHtml(str)}</code></pre>`;
    }
});

export const formatMessage = (content: string) => {
    if (!content) return '';
    const rawHTML = md.render(content);
    return DOMPurify.sanitize(rawHTML);
};
