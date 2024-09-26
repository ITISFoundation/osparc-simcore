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

  construct: function(newStudiesData) {
    this.base(arguments);

    const newButtonsInfo = newStudiesData.resources;
    this.__groups = newStudiesData.categories || [];
    this.__groupedContainers = [];

    this._setLayout(new qx.ui.layout.VBox(10));

    const flatList = this.__flatList = new osparc.dashboard.ToggleButtonContainer();
    [
      "changeSelection",
      "changeVisibility"
    ].forEach(signalName => {
      flatList.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
    });
    this._add(this.__flatList);

    osparc.data.Resources.get("templates")
      .then(templates => {
        const displayTemplates = newButtonsInfo.filter(newButtonInfo => {
          if (newButtonInfo.showDisabled) {
            return true;
          }
          return templates.find(t => t.name === newButtonInfo.expectedTemplateLabel);
        });
        this.__newStudies = displayTemplates;
      })
      .catch(console.error)
      .finally(() => this.fireEvent("templatesLoaded"));
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
    "templatesLoaded": "qx.event.type.Event",
    "newStudyClicked": "qx.event.type.Data",
  },

  statics: {
    WIDTH: 600
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

      const newCards = [];
      this.__newStudies.forEach(resourceData => {
        const cards = this.__resourceToCards(resourceData);
        cards.forEach(newCard => {
          newCard.setEnabled(!(resourceData.showDisabled));
          newCards.push(newCard);
        });
      });
      return newCards;
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
      atom.set({
        font: "text-16",
        maxWidth: this.self().WIDTH
      });
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
      let desc = templateInfo.description;
      if (desc) {
        desc = osparc.utils.Utils.replaceTokens(
          desc,
          "replace_me_product_name",
          osparc.store.StaticInfo.getInstance().getDisplayName()
        );
      }
      const newPlanButton = new osparc.dashboard.GridButtonNew(title, desc);
      newPlanButton.setCardKey(templateInfo.idToWidget);
      osparc.utils.Utils.setIdToWidget(newPlanButton, templateInfo.idToWidget);
      newPlanButton.addListener("execute", () => newStudyClicked());
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
