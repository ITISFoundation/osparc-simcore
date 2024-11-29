/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.GridButtonItem", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function() {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.ITEM);

    this.addListener("changeValue", this.__itemSelected, this);
  },

  statics: {
    MENU_BTN_DIMENSIONS: 24
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      let layout;
      switch (id) {
        case "tsr-rating":
          control = osparc.dashboard.CardBase.createTSRLayout();
          layout = this.getChildControl("footer");
          layout.add(control, osparc.dashboard.GridButtonBase.FPOS.TSR);
          break;
        case "workbench-mode":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            padding: [0, 5]
          });
          layout = this.getChildControl("footer");
          layout.add(control, osparc.dashboard.GridButtonBase.FPOS.UI_MODE);
          break;
        case "empty-workbench": {
          control = this._getEmptyWorkbenchIcon();
          layout = this.getChildControl("footer");
          layout.add(control, osparc.dashboard.GridButtonBase.FPOS.UPDATES);
          break;
        }
        case "update-study":
          control = new qx.ui.basic.Image().set({
            source: "@MaterialIcons/update/16",
            visibility: "excluded",
            alignY: "middle",
            padding: [0, 5]
          });
          osparc.utils.Utils.setIdToWidget(control, "updateStudyBtn");
          layout = this.getChildControl("footer");
          layout.add(control, osparc.dashboard.GridButtonBase.FPOS.UPDATES);
          break;
        case "hits-service":
          control = new qx.ui.basic.Label().set({
            toolTipText: this.tr("Number of times you instantiated it"),
            alignY: "middle"
          });
          layout = this.getChildControl("footer");
          layout.add(control, osparc.dashboard.GridButtonBase.FPOS.HITS);
          break;
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 3)).set({
            anonymous: true,
            paddingLeft: osparc.dashboard.GridButtonBase.PADDING,
            paddingRight: osparc.dashboard.GridButtonBase.PADDING,
            paddingBottom: osparc.dashboard.GridButtonBase.PADDING / 2
          });
          layout = this.getChildControl("main-layout");
          layout.add(control, osparc.dashboard.GridButtonBase.POS.TAGS);
          break;
        case "menu-button":
          this.getChildControl("title").set({
            maxWidth: osparc.dashboard.GridButtonBase.ITEM_WIDTH - 2*osparc.dashboard.GridButtonBase.PADDING - this.self().MENU_BTN_DIMENSIONS
          });
          control = new qx.ui.form.MenuButton().set({
            appearance: "form-button-outlined",
            width: this.self().MENU_BTN_DIMENSIONS,
            height: this.self().MENU_BTN_DIMENSIONS,
            padding: [0, 8, 0, 8],
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          this._add(control, {
            top: 8,
            right: 8
          });
          break;
        case "tick-unselected":
          control = new qx.ui.basic.Atom().set({
            appearance: "form-button-outlined",
            width: this.self().MENU_BTN_DIMENSIONS,
            height: this.self().MENU_BTN_DIMENSIONS,
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
          });
          this._add(control, {
            top: 8,
            right: 8
          });
          break;
        case "tick-selected":
          control = new qx.ui.basic.Image().set({
            appearance: "form-button",
            width: this.self().MENU_BTN_DIMENSIONS,
            height: this.self().MENU_BTN_DIMENSIONS,
            padding: 5,
            alignX: "center",
            alignY: "middle",
            source: "@FontAwesome5Solid/check/12",
            focusable: false
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
          });
          this._add(control, {
            top: 8,
            right: 8
          });
          break;
        case "lock-status":
          control = new osparc.ui.basic.Thumbnail();
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        case "permission-icon":
          control = new qx.ui.basic.Image(osparc.dashboard.CardBase.PERM_READ).set({
            alignY: "middle",
            padding: [0, 5],
            toolTipText: this.tr("Viewer only")
          });
          layout = this.getChildControl("footer");
          layout.add(control, osparc.dashboard.GridButtonBase.FPOS.PERMISSION);
          break;
      }

      return control || this.base(arguments, id);
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
      const menuButton = this.getChildControl("menu-button");
      menuButton.setVisibility("visible");
      const tick = this.getChildControl("tick-selected");
      tick.setVisibility("excluded");
      const untick = this.getChildControl("tick-unselected");
      untick.setVisibility("excluded");
    },

    // overridden
    _applyLastChangeDate: function(value, old) {
      if (value && (this.isResourceType("study") || this.isResourceType("template"))) {
        const label = this.getChildControl("modified-text");
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

    // overridden
    _applyOwner: function(value, old) {
      const label = this.getChildControl("subtitle-text");
      const user = this.__createOwner(value);
      label.setValue(user);
      label.setVisibility(value ? "visible" : "excluded");
    },

    _applyAccessRights: function(value) {
      if (value && Object.keys(value).length) {
        const shareIcon = this.getChildControl("subtitle-icon");
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
        tagsContainer.setVisibility(tags.length ? "visible" : "excluded");
        tagsContainer.removeAll();
        tags.forEach(tag => {
          const tagUI = new osparc.ui.basic.Tag(tag, "searchBarFilter");
          tagUI.set({
            font: "text-12",
            toolTipText: this.tr("Click to filter by this Tag")
          });
          tagUI.addListener("tap", () => this.fireDataEvent("tagClicked", tag));
          tagsContainer.add(tagUI);
        });
      }
    },

    // overridden
    _applyMenu: function(menu, old) {
      const menuButton = this.getChildControl("menu-button");
      if (menu) {
        menuButton.setMenu(menu);
        menu.setPosition("top-left");
        osparc.utils.Utils.prettifyMenu(menu);
        osparc.utils.Utils.setIdToWidget(menu, "studyItemMenuMenu");
        this.evaluateMenuButtons();
      }
      menuButton.setVisibility(menu ? "visible" : "excluded");
    }
  }
});
