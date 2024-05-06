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

  construct: function(newStudies) {
    this.base(arguments);

    this.__newStudies = newStudies;

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
    mode: {
      check: ["grid", "list"],
      init: "grid",
      nullable: false,
      event: "changeMode",
      apply: "reloadCards"
    },

    groupBy: {
      check: [null, "category"],
      init: null,
      nullable: true
    }
  },

  events: {
    "newStudyClicked": "qx.event.type.Data"
  },

  members: {
    __newStudies: null,
    __flatList: null,
    __groupedContainers: null,

    reloadCards: function(listId) {
      this.__cleanAll();

      if (this.getGroupBy()) {
        const noGroupContainer = this.__createGroupContainer("no-group", "No Group", "transparent");
        this._add(noGroupContainer);

        const categories = new Set([]);
        this.__newStudies.forEach(newStudy => newStudy.category && categories.add(newStudy.category));
        Array.from(categories).forEach(category => {
          const groupContainer = this.__createGroupContainer(category, qx.lang.String.firstUp(category), "transparent");
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
        const spacing = this.getMode() === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
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
      const title = templateInfo.title;
      const desc = templateInfo.description;
      const mode = this.getMode();
      const newPlanButton = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
      newPlanButton.setCardKey(templateInfo.idToWidget);
      osparc.utils.Utils.setIdToWidget(newPlanButton, templateInfo.idToWidget);
      if (this.getMode() === "list") {
        const width = this.getBounds().width - 15;
        newPlanButton.setWidth(width);
      }
      newPlanButton.addListener("execute", () => this.fireDataEvent("newStudyClicked", templateInfo))
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
