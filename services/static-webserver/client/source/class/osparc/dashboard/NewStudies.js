/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.NewStudies", {
  extend: qx.ui.core.Widget,

  construct: function(newStudies, groups) {
    this.base(arguments);

    this.__newStudies = newStudies;
    this.__groups = groups || [];

    this._setLayout(new qx.ui.layout.VBox(10));

    const flatList = this.__flatList = new osparc.dashboard.ToggleButtonContainer();
    [
      "changeSelection",
      "changeVisibility"
    ].forEach(signalName => {
      flatList.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
    });
    this._add(this.__flatList);

    this.__groupedContainers = [];
  },

  properties: {
    groupBy: {
      check: [null, "category"],
      init: null,
      nullable: true,
      apply: "reloadCards"
    }
  },

  events: {
    "newStudyClicked": "qx.event.type.Data"
  },

  members: {
    __newStudies: null,
    __groups: null,
    __flatList: null,
    __groupedContainers: null,

    reloadCards: function(listId) {
      this.__cleanAll();

      if (this.getGroupBy()) {
        const noGroupContainer = this.__createGroupContainer("no-group", "No Group", "transparent");
        this._add(noGroupContainer);

        Array.from(this.__groups).forEach(group => {
          const groupContainer = this.__createGroupContainer(group.id, group.label, "transparent");
          this._add(groupContainer);
        });
      } else {
        const flatList = this.__flatList = new osparc.dashboard.ToggleButtonContainer();
        osparc.utils.Utils.setIdToWidget(flatList, listId);
        [
          "changeSelection",
          "changeVisibility"
        ].forEach(signalName => {
          flatList.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
        });
        const spacing = osparc.dashboard.GridButtonBase.SPACING;
        this.__flatList.getLayout().set({
          spacingX: spacing,
          spacingY: spacing
        });
        this._add(this.__flatList);
      }

      let cards = [];
      this.__newStudies.forEach(resourceData => {
        Array.prototype.push.apply(cards, this.__resourceToCards(resourceData));
      });
      return cards;
    },

    __resourceToCards: function(resourceData) {
      const cards = [];
      if (this.getGroupBy() === "category") {
        this.__groupByCategory(cards, resourceData);
      } else {
        const card = this.__createCard(resourceData);
        cards.push(card);
        this.__flatList.add(card);
      }
      return cards;
    },

    __groupByCategory: function(cards, resourceData) {
      const card = this.__createCard(resourceData);
      const groupContainer = this.__getGroupContainer(resourceData.category);
      if (groupContainer) {
        groupContainer.add(card);
      } else {
        let noGroupContainer = this.__getGroupContainer("no-group");
        noGroupContainer.add(card);
      }
      cards.push(card);
    },

    __createGroupContainer: function(groupId, headerLabel, headerColor = "text") {
      const groupContainer = new osparc.dashboard.GroupedToggleButtonContainer().set({
        groupId: groupId.toString(),
        headerLabel,
        headerIcon: "",
        headerColor,
        visibility: "excluded"
      });
      osparc.utils.Utils.setIdToWidget(groupContainer, groupId.toString() + "Group");
      const atom = groupContainer.getChildControl("header");
      atom.setFont("text-16");
      this.__groupedContainers.push(groupContainer);
      return groupContainer;
    },

    __getGroupContainer: function(gid) {
      const idx = this.__groupedContainers.findIndex(groupContainer => groupContainer.getGroupId() === gid.toString());
      if (idx > -1) {
        return this.__groupedContainers[idx];
      }
      return null;
    },

    __createCard: function(templateInfo) {
      const newStudyClicked = () => this.fireDataEvent("newStudyClicked", templateInfo);

      const title = templateInfo.title;
      const desc = templateInfo.description;
      const newPlanButton = new osparc.dashboard.GridButtonNew(title, desc);
      newPlanButton.setCardKey(templateInfo.idToWidget);
      osparc.utils.Utils.setIdToWidget(newPlanButton, templateInfo.idToWidget);
      if (templateInfo.billable) {
        // replace the plus button with the creditsImage
        const creditsImage = new osparc.desktop.credits.CreditsImage();
        creditsImage.getChildControl("image").set({
          width: 60,
          height: 60
        })
        newPlanButton.replaceIcon(creditsImage);

        newPlanButton.addListener("execute", () => {
          const store = osparc.store.Store.getInstance();
          const credits = store.getContextWallet().getCreditsAvailable()
          const preferencesSettings = osparc.Preferences.getInstance();
          const warningThreshold = preferencesSettings.getCreditsWarningThreshold();
          if (credits <= warningThreshold) {
            const msg = this.tr("This Plan requires Credits to run Sim4Life powered simulations. You can top up in the Billing Center.");
            const win = new osparc.ui.window.Confirmation(msg).set({
              caption: this.tr("Credits required"),
              confirmText: this.tr("Start, I'll get them later"),
              confirmAction: "create"
            });
            win.center();
            win.open();
            win.addListener("close", () => {
              if (win.getConfirmed()) {
                this.fireDataEvent("newStudyClicked", templateInfo);
              }
            });
          } else {
            newStudyClicked();
          }
        });
      } else {
        newPlanButton.addListener("execute", () => newStudyClicked());
      }
      return newPlanButton;
    },

    __cleanAll: function() {
      if (this.__flatList) {
        this.__flatList.removeAll();
        this.__flatList = null;
      }
      this.__groupedContainers.forEach(groupedContainer => groupedContainer.getContentContainer().removeAll());
      this.__groupedContainers = [];
      this._removeAll();
    },

    __moveNoGroupToLast: function() {
      const idx = this._getChildren().findIndex(grpContainer => grpContainer === this.__getGroupContainer("no-group"));
      if (idx > -1) {
        this._getChildren().push(this._getChildren().splice(idx, 1)[0]);
      }
    }
  }
});
