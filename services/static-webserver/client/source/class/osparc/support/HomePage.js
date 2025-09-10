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
    this.getChildControl("ask-a-question");
    this.__populateButtons();
  },

  events: {
    "openConversation": "qx.event.type.Event",
  },

  statics: {
    decorateButton: function(button) {
      button.set({
        font: "text-14",
        gap: 10,
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
            appearance: "strong-button",
            font: "text-14",
            center: true,
          });
          control.addListener("execute", () => this.fireEvent("openConversation"));
          this._add(control);
          break;
        case "links-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __populateButtons: function() {
      const quickStartButton = osparc.store.Support.getQuickStartButton();
      if (quickStartButton) {
        this.getChildControl("links-layout").add(quickStartButton);
        this.self().decorateButton(quickStartButton);
      }

      const guidedToursButton = osparc.store.Support.getGuidedToursButton();
      this.getChildControl("links-layout").add(guidedToursButton);
      this.self().decorateButton(guidedToursButton);

      const permissions = osparc.data.Permissions.getInstance();
      if (permissions.canDo("dashboard.templates.read")) {
        const tutorialsBtn = new qx.ui.form.Button(this.tr("Tutorials"), "@FontAwesome5Solid/graduation-cap/14");
        this.getChildControl("links-layout").add(tutorialsBtn);
        this.self().decorateButton(tutorialsBtn);
      }

      const manualButtons = osparc.store.Support.getManualButtons();
      manualButtons.forEach(manualButton => {
        this.getChildControl("links-layout").add(manualButton);
        this.self().decorateButton(manualButton);
      });

      const supportButtons = osparc.store.Support.getSupportButtons();
      supportButtons.forEach(supportButton => {
        this.getChildControl("links-layout").add(supportButton);
        this.self().decorateButton(supportButton);
      });

      const releaseNotesButton = osparc.store.Support.getReleaseNotesButton();
      this.getChildControl("links-layout").add(releaseNotesButton);
      this.self().decorateButton(releaseNotesButton);
    },
  }
});
