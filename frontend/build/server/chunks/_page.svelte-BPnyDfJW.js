import { P as ensure_array_like, Q as attr_class, T as clsx, O as attr } from './index-Bc7Px9cs.js';
import markdownit from 'markdown-it';
import DOMPurify from 'isomorphic-dompurify';
import hljs from 'highlight.js';
import { e as escape_html } from './context-R2425nfV.js';

function html(value) {
  var html2 = String(value ?? "");
  var open = "<!---->";
  return open + html2 + "<!---->";
}
const nouvelleDiscussion = "data:image/svg+xml,%3c?xml%20version='1.0'%20encoding='UTF-8'?%3e%3csvg%20xmlns='http://www.w3.org/2000/svg'%20id='Bold'%20viewBox='0%200%2024%2024'%20width='512'%20height='512'%3e%3cpath%20d='M16.5,10.5h-3v-3a1.5,1.5,0,0,0-3,0v3h-3a1.5,1.5,0,0,0,0,3h3v3a1.5,1.5,0,0,0,3,0v-3h3a1.5,1.5,0,0,0,0-3Z'/%3e%3c/svg%3e";
function escapeHtml(unsafe) {
  return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
const md = markdownit({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="highlight" data-language="${lang.toUpperCase()}"><code>${hljs.highlight(str, { language: lang, ignoreIllegals: true }).value}</code></pre>`;
      } catch {
      }
    }
    return `<pre class="highlight"><code>${escapeHtml(str)}</code></pre>`;
  }
});
const formatMessage = (content) => {
  if (!content) return "";
  const rawHTML = md.render(content);
  return DOMPurify.sanitize(rawHTML);
};
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let messages = [
      {
        role: "assistant",
        content: "Salut ! je suis ton assistant J.E.A.N-H.E.U.D.E"
      }
    ];
    let sessionActive = null;
    let historiques = [];
    let currentMessage = "";
    let attente = false;
    $$renderer2.push(`<div class="container-global svelte-1uha8ag"><div class="historique-windows svelte-1uha8ag"><h2 class="historique-titre svelte-1uha8ag">Historique des conversations</h2> <!--[-->`);
    const each_array = ensure_array_like(historiques);
    for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
      let historique = each_array[$$index];
      $$renderer2.push(`<button${attr_class("message-historique svelte-1uha8ag", void 0, { "active": sessionActive === historique.id })}>${escape_html(historique.resume)}</button>`);
    }
    $$renderer2.push(`<!--]--></div> <div class="chat-box svelte-1uha8ag"><div class="chat-widows svelte-1uha8ag"><!--[-->`);
    const each_array_1 = ensure_array_like(messages);
    for (let $$index_1 = 0, $$length = each_array_1.length; $$index_1 < $$length; $$index_1++) {
      let msg = each_array_1[$$index_1];
      $$renderer2.push(`<div${attr_class(clsx(msg.role), "svelte-1uha8ag")}><div class="message-content svelte-1uha8ag">${html(formatMessage(msg.content))}</div></div>`);
    }
    $$renderer2.push(`<!--]--></div> <form class="chatter svelte-1uha8ag"><input class="chat svelte-1uha8ag"${attr("value", currentMessage)} placeholder="pose ta question ..."/> <button class="button-go svelte-1uha8ag"${attr("disabled", attente, true)} type="submit">Envoyer</button> <button class="new-chat svelte-1uha8ag" aria-label="Commencer une nouvelle discussion" title="Nouvelle discussion"><img${attr("src", nouvelleDiscussion)} aria-hidden="true" alt="" class="svelte-1uha8ag"/></button></form></div></div>`);
  });
}

export { _page as default };
//# sourceMappingURL=_page.svelte-BPnyDfJW.js.map
