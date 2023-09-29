/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.ListButtonItem", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function() {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.ITEM);

    this.addListener("changeValue", this.__itemSelected, this);
  },

  statics: {
    MENU_BTN_WIDTH: 25
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "lock-status":
          control = new osparc.ui.basic.Thumbnail().set({
            minWidth: 40
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.LOCK_STATUS
          });
          break;
        case "permission-icon":
          control = new qx.ui.basic.Image().set({
            minWidth: 50
          });
          control.exclude();
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.PERMISSION
          });
          break;
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
            alignY: "middle"
          })).set({
            anonymous: true,
            maxWidth: 100
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TAGS
          });
          break;
        case "shared-icon":
          control = new qx.ui.basic.Image().set({
            minWidth: 50,
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.SHARED
          });
          break;
        case "last-change":
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-13",
            allowGrowY: false,
            minWidth: 120,
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.LAST_CHANGE
          });
          break;
        case "tsr-rating":
          control = osparc.dashboard.CardBase.createTSRLayout();
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TSR
          });
          break;
        case "workbench-mode":
          control = new qx.ui.basic.Image().set({
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.UI_MODE
          });
          break;
        case "hits-service":
          control = new qx.ui.basic.Label().set({
            alignY: "middle",
            toolTipText: this.tr("Number of times you instantiated it")
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.HITS
          });
          break;
        case "empty-workbench":
          control = this._getEmptyWorkbenchIcon();
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.UPDATES
          });
          break;
        case "update-study":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            source: "@MaterialIcons/update/18",
            visibility: "excluded"
          });
          osparc.utils.Utils.setIdToWidget(control, "updateStudyBtn");
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.UPDATES
          });
          break;
        case "menu-selection-stack":
          control = new qx.ui.container.Stack().set({
            minWidth: this.self().MENU_BTN_WIDTH,
            minHeight: this.self().MENU_BTN_WIDTH,
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.OPTIONS
          });
          break;
        case "tick-unselected": {
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/16");
          menuSelectionStack.addAt(control, 1);
          break;
        }
        case "tick-selected": {
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          control = new qx.ui.basic.Image("@FontAwesome5Solid/check-circle/16");
          menuSelectionStack.addAt(control, 2);
          break;
        }
        case "menu-button": {
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          control = new qx.ui.form.MenuButton().set({
            width: this.self().MENU_BTN_WIDTH,
            height: this.self().MENU_BTN_WIDTH,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": parseInt(this.self().MENU_BTN_WIDTH/2) + "px"
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          menuSelectionStack.addAt(control, 0);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _applyLastChangeDate: function(value, old) {
      if (value) {
        const label = this.getChildControl("last-change");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    // overridden
    _applyOwner: function(value, old) {
      return;
    },

    _applyAccessRights: function(value) {
      if (value && Object.keys(value).length) {
        const shareIcon = this.getChildControl("shared-icon");
        this._evaluateShareIcon(shareIcon, value);
      }
    },

    _applyTags: function(tags) {
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        const tagsContainer = this.getChildControl("tags");
        tagsContainer.removeAll();
        tags.forEach(tag => {
          const tagUI = new osparc.ui.basic.Tag(tag.name, tag.color, "searchBarFilter").set({
            alignY: "middle",
            font: "text-12"
          });
          tagUI.addListener("tap", () => this.fireDataEvent("tagClicked", tag));
          tagsContainer.add(tagUI);
        });
      }
    },

    // overridden
    _applyMultiSelectionMode: function(value) {
      if (value) {
        const menuButton = this.getChildControl("menu-button");
        menuButton.setVisibility("excluded");
        this.__itemSelected();
      } else {
        this.__showMenuOnly();
      }
    },

    __itemSelected: function() {
      if (this.isResourceType("study") && this.isMultiSelectionMode()) {
        const selected = this.getValue();

        if (this.isLocked() && selected) {
          this.setValue(false);
        }

        const tick = this.getChildControl("tick-selected");
        const untick = this.getChildControl("tick-unselected");
        this.getChildControl("menu-selection-stack").setSelection([selected ? tick : untick]);
      } else {
        this.__showMenuOnly();
      }
    },

    __showMenuOnly: function() {
      const menu = this.getChildControl("menu-button");
      this.getChildControl("menu-selection-stack").setSelection([menu]);
    },

    _applyMenu: function(value, old) {
      const menuButton = this.getChildControl("menu-button");
      if (value) {
        menuButton.setMenu(value);
        osparc.utils.Utils.setIdToWidget(value, "studyItemMenuMenu");
      }
      menuButton.setVisibility(value ? "visible" : "excluded");
    }
  }
});
