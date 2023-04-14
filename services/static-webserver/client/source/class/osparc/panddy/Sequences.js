/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.panddy.Sequences", {
  extend: osparc.ui.basic.FloatingHelper,

  construct: function(element, sequences) {
    this.base(arguments, element);

    this.setLayout(new qx.ui.layout.VBox(8));

    const hintContainer = this.getChildControl("hint-container");
    hintContainer.setPadding(15);
    hintContainer.getContentElement().setStyles({
      "border-radius": "8px"
    });

    this.getChildControl("title");
    this.getChildControl("sequences-layout");

    if (sequences) {
      this.setSequences(sequences);
    }
  },

  events: {
    "sequenceSelected": "qx.event.type.Data"
  },

  properties: {
    sequences: {
      check: "Array",
      init: [],
      nullable: true,
      apply: "__applySequences"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Tutorials:"),
            font: "text-14"
          });
          this.add(control);
          break;
        case "sequences-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __isSelectorVisible: function(doc, selector) {
      const domEl = doc.querySelector(`[${selector}]`);
      if (domEl) {
        const domWidget = qx.ui.core.Widget.getWidgetByElement(domEl);
        if (qx.ui.core.queue.Visibility.isVisible(domWidget)) {
          return true;
        }
      }
      return false;
    },

    __evaluateRequiredTarget: function(sequence, seqButton) {
      if (this.__isSelectorVisible(document, sequence.requiredTarget)) {
        seqButton.setEnabled(true);
        return;
      }
      const iframes = document.querySelectorAll("iframe");
      for (let i=0; i<iframes.length; i++) {
        if (this.__isSelectorVisible(iframes[i].contentWindow.document, sequence.requiredTarget)) {
          seqButton.setEnabled(true);
          return;
        }
      }
      seqButton.setEnabled(false);
    },

    __getSequenceButton: function(sequence) {
      const seqButton = new qx.ui.form.Button().set({
        label: sequence.name,
        icon: "@FontAwesome5Solid/arrow-right/14",
        iconPosition: "right",
        alignX: "left",
        rich: true,
        toolTipText: sequence.description
      });
      if (sequence.requiredTarget) {
        this.__evaluateRequiredTarget(sequence, seqButton);
      }
      seqButton.addListener("execute", () => this.fireDataEvent("sequenceSelected", sequence), this);
      return seqButton;
    },

    __applySequences: function(seqs) {
      const sequencesLayout = this.getChildControl("sequences-layout");
      seqs.forEach(seq => sequencesLayout.add(this.__getSequenceButton(seq)));
    }
  }
});
