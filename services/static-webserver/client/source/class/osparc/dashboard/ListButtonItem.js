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
    MENU_BTN_DIMENSIONS: 24
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
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
            alignY: "middle"
          })).set({
            anonymous: true,
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TAGS
          });
          break;
        case "shared-icon":
          control = new qx.ui.basic.Image().set({
            minWidth: 30,
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
          this.__makeItemResponsive(control);
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TSR
          });
          break;
        case "permission-icon":
          control = new qx.ui.basic.Image(osparc.dashboard.CardBase.PERM_READ).set({
            alignY: "middle",
          });
          this.getChildControl("icons-layout").add(control);
          break;
        case "workbench-mode":
          control = new qx.ui.basic.Image().set({
            alignY: "middle"
          });
          this.getChildControl("icons-layout").add(control);
          break;
        case "empty-workbench":
          control = this._getEmptyWorkbenchIcon();
          control.set({
            alignY: "middle",
            alignX: "center"
          });
          this.getChildControl("icons-layout").add(control);
          break;
        case "update-study":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            source: "@MaterialIcons/update/18",
            visibility: "excluded"
          });
          osparc.utils.Utils.setIdToWidget(control, "updateStudyBtn");
          this.getChildControl("icons-layout").add(control);
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
        case "menu-selection-stack":
          control = new qx.ui.container.Stack();
          control.set({
            alignX: "center",
            alignY: "middle"
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.OPTIONS
          });
          break;
        case "tick-unselected": {
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          control = new qx.ui.basic.Atom().set({
            appearance: "form-button-outlined",
            width: this.self().MENU_BTN_DIMENSIONS,
            height: this.self().MENU_BTN_DIMENSIONS,
            focusable: false
          });
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
          });
          menuSelectionStack.addAt(control, 1);
          break;
        }
        case "tick-selected": {
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          control = new qx.ui.basic.Image("@FontAwesome5Solid/check/12").set({
            appearance: "form-button-outlined",
            width: this.self().MENU_BTN_DIMENSIONS,
            height: this.self().MENU_BTN_DIMENSIONS,
            padding: [6, 5],
            focusable: false
          });
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
          });
          menuSelectionStack.addAt(control, 2);
          break;
        }
        case "menu-button": {
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          control = new qx.ui.form.MenuButton().set({
            appearance: "form-button-outlined",
            padding: [0, 8],
            maxWidth: this.self().MENU_BTN_DIMENSIONS,
            maxHeight: this.self().MENU_BTN_DIMENSIONS,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
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

    __createOwner: function(label) {
      if (label === osparc.auth.Data.getInstance().getEmail()) {
        const resourceAlias = osparc.utils.Utils.resourceTypeToAlias(this.getResourceType());
        return qx.locale.Manager.tr(`My ${resourceAlias}`);
      }
      return osparc.utils.Utils.getNameFromEmail(label);
    },

    _applyOwner: function(value, old) {
      const label = this.getChildControl("owner");
      const user = this.__createOwner(value);
      label.setValue(user);
      this.__makeItemResponsive(label);
      return;
    },

    _applyAccessRights: function(value) {
      if (value && Object.keys(value).length) {
        const shareIcon = this.getChildControl("shared-icon");
        shareIcon.addListener("tap", e => {
          e.stopPropagation();
          this.openAccessRights();
        }, this);
        shareIcon.addListener("pointerdown", e => e.stopPropagation());
        osparc.dashboard.CardBase.populateShareIcon(shareIcon, value);

        if (this.isResourceType("study")) {
          this._setStudyPermissions(value);
        }
      }
    },

    _applyTags: function(tags) {
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        const tagsContainer = this.getChildControl("tags");
        tagsContainer.removeAll();
        tags.forEach(tag => {
          const tagUI = new osparc.ui.basic.Tag(tag, "searchBarFilter");
          tagUI.set({
            alignY: "middle",
            font: "text-12",
            toolTipText: this.tr("Click to filter by this Tag")
          });
          tagUI.addListener("tap", () => this.fireDataEvent("tagClicked", tag));
          tagsContainer.add(tagUI);
        });
        this.__makeItemResponsive(tagsContainer);
      }
    },

    __makeItemResponsive: function(item) {
      [
        "appear",
        "resize",
      ].forEach(ev => {
        this.addListener(ev, () => {
          const bounds = this.getBounds() || this.getSizeHint();
          item.setVisibility(bounds.width > 700 ? "visible" : "excluded");
        });
      });
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
      if (this.isItemNotClickable()) {
        this.setValue(false);
        return;
      }

      if (this.isResourceType("study") && this.isMultiSelectionMode()) {
        const selected = this.getValue();

        const tick = this.getChildControl("tick-selected");
        tick.setVisibility(selected ? "visible" : "excluded");

        const untick = this.getChildControl("tick-unselected");
        untick.setVisibility(selected ? "excluded" : "visible");
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
