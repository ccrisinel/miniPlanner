// Deplacement des cartes (SortableJS) + focus des champs rendus par htmx.
(function () {
    "use strict";

    // Etat complet du tableau : "personId:cardId,cardId;personId:cardId"
    function boardState() {
        return Array.from(document.querySelectorAll("[data-cards]"))
            .map(function (list) {
                var ids = Array.from(list.querySelectorAll("[data-card]"))
                    .map(function (card) { return card.dataset.card; });
                return list.dataset.cards + ":" + ids.join(",");
            })
            .join(";");
    }

    function persistOrder() {
        htmx.ajax("POST", "/reorder", { values: { state: boardState() }, swap: "none" });
    }

    function selfAndDescendants(root, selector) {
        var found = Array.from(root.querySelectorAll ? root.querySelectorAll(selector) : []);
        if (root.matches && root.matches(selector)) found.unshift(root);
        return found;
    }

    function initSortable(root) {
        selfAndDescendants(root, "[data-cards]").forEach(function (list) {
            if (list.sortableReady) return;
            list.sortableReady = true;
            new Sortable(list, {
                group: "cards",
                animation: 150,
                // les controles restent cliquables, on tire la carte par ses marges
                filter: "button, input, textarea, form",
                preventOnFilter: false,
                ghostClass: "card-ghost",
                onEnd: persistOrder,
            });
        });
    }

    // Cliquer ailleurs vaut validation : on soumet ce qui est rempli, on abandonne ce
    // qui est vide (la carte en cours de creation disparait alors d'elle-meme).
    function armCommitOnBlur(root) {
        selfAndDescendants(root, "[data-commit]").forEach(function (input) {
            if (input.commitArmed || !input.form) return;
            input.commitArmed = true;
            var form = input.form;

            // Entree et Echap passent deja par htmx : ne pas rejouer au blur qui suit.
            form.addEventListener("htmx:before:request", function () { input.done = true; });
            input.addEventListener("focus", function () { input.done = false; });

            input.addEventListener("blur", function () {
                if (input.done) return;
                if (input.value.trim()) {
                    input.done = true;
                    form.requestSubmit();
                    return;
                }
                // vide : on rejoue l'annulation deja decrite pour Echap, s'il y en a une
                var cancel = input.getAttribute("hx-get");
                if (!cancel) return;
                input.done = true;
                htmx.ajax("GET", cancel, {
                    target: input.getAttribute("hx-target"),
                    swap: input.getAttribute("hx-swap"),
                });
            });
        });
    }

    function focusPending(root) {
        var field = selfAndDescendants(root, "[data-autofocus]")[0];
        if (!field) return;
        field.focus();
        if (field.select) field.select();
    }

    function process(root) {
        initSortable(root);
        armCommitOnBlur(root);
        focusPending(root);
    }

    htmx.onLoad(process);
    document.addEventListener("DOMContentLoaded", function () { process(document.body); });
})();
