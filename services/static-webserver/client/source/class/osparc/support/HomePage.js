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

    this.getChildControl("conversations-intro-text");
    if (osparc.store.Groups.getInstance().isSupportEnabled()) {
      this.getChildControl("ask-a-question");
    }
    this.__populateButtons();
  },

  events: {
    "openConversation": "qx.event.type.Event",
  },

  statics: {
    decorateButton: function(button) {
      button.set({
        appearance: "help-list-button",
        icon: null,
        gap: 8,
        paddingLeft: 16,
      });
      button.getChildControl("label").set({
        rich: true
      });
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversations-intro-text": {
          control = new qx.ui.basic.Label().set({
            rich: true,
            font: "text-16",
          });
          const isSupportUser = osparc.store.Groups.getInstance().amIASupportUser();
          const userName = osparc.auth.Data.getInstance().getUserName();
          control.set({
            value: isSupportUser ?
              userName + ", " + this.tr("thanks for being here!<br>Let's help every user feel supported.") :
              this.tr("Hi there 👋<br>How can we help?"),
          });
          this._add(control);
          break;
        }
        case "ask-a-question":
          control = new qx.ui.form.Button(this.tr("Ask a Question"), "@FontAwesome5Solid/comments/16").set({
            gap: 8,
            appearance: "strong-button",
            center: true,
          });
          control.addListener("execute", () => this.fireEvent("openConversation"));
          this._add(control);
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
      const learningBox = this.getChildControl("learning-box");
      const quickStartButton = osparc.store.Support.getQuickStartButton();
      if (quickStartButton) {
        learningBox.add(quickStartButton);
        this.self().decorateButton(quickStartButton);
      }

      const permissions = osparc.data.Permissions.getInstance();
      if (permissions.canDo("dashboard.templates.read")) {
        const tutorialsBtn = new qx.ui.form.Button(this.tr("Explore Tutorials"), "@FontAwesome5Solid/graduation-cap/14");
        learningBox.add(tutorialsBtn);
        this.self().decorateButton(tutorialsBtn);
      }

      const guidedToursButton = osparc.store.Support.getGuidedToursButton();
      learningBox.add(guidedToursButton);
      this.self().decorateButton(guidedToursButton);

      const referencesBox = this.getChildControl("references-box");
      const manualButtons = osparc.store.Support.getManualButtons();
      manualButtons.forEach(manualButton => {
        referencesBox.add(manualButton);
        this.self().decorateButton(manualButton);
      });

      const supportButtons = osparc.store.Support.getSupportButtons();
      supportButtons.forEach(supportButton => {
        referencesBox.add(supportButton);
        this.self().decorateButton(supportButton);
      });

      const releaseNotesButton = osparc.store.Support.getReleaseNotesButton();
      this._add(releaseNotesButton);
      this.self().decorateButton(releaseNotesButton);
      releaseNotesButton.set({
        icon: "@FontAwesome5Solid/bullhorn/14",
        // align it with the rest of the buttons in section boxes
        marginLeft: 11,
        marginRight: 11,
      });
    },
  }
});
