/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.support.HomePage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.set({
      padding: 5,
    });

    if (osparc.store.Groups.getInstance().isSupportEnabled()) {
      this.getChildControl("ask-a-question-button");
      this.getChildControl("book-a-call-button");
      if (osparc.product.Utils.isBookACallEnabled()) {
        this.getChildControl("book-a-call-button-3rd");
      }
    }
    this.__populateButtons();
  },

  events: {
    "createConversation": "qx.event.type.Data",
  },

  statics: {
    decorateButton: function(button) {
      button.set({
        appearance: "help-list-button",
        icon: null,
        gap: 8,
        paddingLeft: 12,
        paddingRight: 12,
      });
      button.getChildControl("label").set({
        rich: true
      });
    },

    addExternalLinkIcon: function(button) {
      const icon = new qx.ui.basic.Image("@FontAwesome5Solid/external-link-alt/14").set({
        alignY: "middle",
        marginLeft: 5
      });
      button._add(icon);
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversation-buttons-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
            // align it with the rest of the buttons in section boxes
            marginLeft: 11,
            marginRight: 11,
          });
          this._add(control);
          break;
        }
        case "ask-a-question-button":
          control = new qx.ui.form.Button(this.tr("Ask a Question"), "@FontAwesome5Solid/comments/16").set({
            gap: 8,
            appearance: "strong-button",
            center: true,
            width: 183,
          });
          control.addListener("execute", () => this.fireDataEvent("createConversation", osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.ASK_A_QUESTION));
          this.getChildControl("conversation-buttons-layout").add(control, { flex: 1 });
          break;
        case "book-a-call-button":
          control = new qx.ui.form.Button(this.tr("Book a Call"), "@FontAwesome5Solid/phone/16").set({
            gap: 8,
            appearance: "strong-button",
            center: true,
            width: 183,
          });
          control.addListener("execute", () => this.fireDataEvent("createConversation", osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL));
          this.getChildControl("conversation-buttons-layout").add(control, { flex: 1 });
          break;
        case "book-a-call-button-3rd":
          control = new qx.ui.form.Button(this.tr("Book a Call"), "@FontAwesome5Solid/flask/16").set({
            gap: 8,
            appearance: "strong-button",
            center: true,
            width: 183,
          });
          control.addListener("execute", () => this.fireDataEvent("createConversation", osparc.support.Conversation.SYSTEM_MESSAGE_TYPE.BOOK_A_CALL_3RD));
          this.getChildControl("conversation-buttons-layout").add(control, { flex: 1 });
          break;
        case "learning-box":
          control = new osparc.widget.SectionBox(this.tr("Learning"), "@FontAwesome5Solid/graduation-cap/14");
          control.getChildControl("legend").set({
            gap: 8
          });
          this._add(control);
          break;
        case "references-box":
          control = new osparc.widget.SectionBox(this.tr("References"), "@FontAwesome5Solid/book/14");
          control.getChildControl("legend").set({
            gap: 8
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __populateButtons: function() {
      const learningButtons = [];
      const quickStartButton = osparc.store.Support.getQuickStartButton();
      if (quickStartButton) {
        learningButtons.push(quickStartButton);
      }
      const permissions = osparc.data.Permissions.getInstance();
      if (permissions.canDo("dashboard.templates.read")) {
        const tutorialsBtn = new qx.ui.form.Button(this.tr("Explore Tutorials"), "@FontAwesome5Solid/graduation-cap/14");
        const store = osparc.store.Store.getInstance();
        store.bind("currentStudy", tutorialsBtn, "enabled", {
          converter: study => !Boolean(study)
        });
        tutorialsBtn.addListener("execute", () => qx.event.message.Bus.getInstance().dispatchByName("showTab", "tutorialsTab"), this);
       learningButtons.push(tutorialsBtn);
      }
      const guidedToursButton = osparc.store.Support.getGuidedToursButton();
      if (guidedToursButton) {
        learningButtons.push(guidedToursButton);
      }
      if (learningButtons.length) {
        const learningBox = this.getChildControl("learning-box");
        learningButtons.forEach(learningButton => {
          learningBox.add(learningButton);
          this.self().decorateButton(learningButton);
        });
      }

      const manualButtons = osparc.store.Support.getManualButtons();
      const supportButtons = osparc.store.Support.getSupportButtons();
      const referenceButtons = manualButtons.concat(supportButtons);
      if (referenceButtons.length) {
        const referencesBox = this.getChildControl("references-box");
        referenceButtons.forEach(referenceButton => {
          referencesBox.add(referenceButton);
          this.self().decorateButton(referenceButton);
          this.self().addExternalLinkIcon(referenceButton);
        });
      }

      const releaseNotesButton = osparc.store.Support.getReleaseNotesButton();
      this._add(releaseNotesButton);
      this.self().decorateButton(releaseNotesButton);
      this.self().addExternalLinkIcon(releaseNotesButton);
      releaseNotesButton.set({
        icon: "@FontAwesome5Solid/bullhorn/14",
        // align it with the rest of the buttons in section boxes
        marginLeft: 11,
        marginRight: 11,
      });
    },
  }
});
