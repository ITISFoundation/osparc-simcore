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
  },

  statics: {
    MENU_BTN_DIMENSIONS: 24,

    BODY_POS: {
      AVATAR_GROUP: 0,
      TAGS: 1,
    },
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
        case "avatar-group": {
          const maxWidth = osparc.dashboard.GridButtonBase.ITEM_WIDTH - osparc.dashboard.GridButtonBase.PADDING * 2;
          control = new osparc.ui.basic.AvatarGroup(24, "left", maxWidth);
          this.getChildControl("body").addAt(control, this.self().BODY_POS.AVATAR_GROUP);
          break;
        }
        case "tags": {
          const wrapper = new qx.ui.container.Composite(new qx.ui.layout.VBox());
          // Add spacer to push tags to bottom
          wrapper.add(new qx.ui.core.Spacer(), {flex: 1});
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(4, 4)).set({
            anonymous: true,
          });
          wrapper.add(control);
          this.getChildControl("body").addAt(wrapper, this.self().BODY_POS.TAGS, {
            flex: 1,
          });
          break;
        }
        case "menu-selection-stack":
          control = new qx.ui.container.Stack();
          control.set({
            alignX: "center",
            alignY: "middle"
          });
          this.getChildControl("header").add(control, {
            column: 2,
            row: 0,
          });
          break;
        case "menu-button": {
          this.getChildControl("title").set({
            maxWidth: osparc.dashboard.GridButtonBase.ITEM_WIDTH - osparc.dashboard.CardBase.ICON_SIZE - this.self().MENU_BTN_DIMENSIONS - 2,
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
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          menuSelectionStack.addAt(control, 0);
          break;
        }
        case "tick-unselected": {
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
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          menuSelectionStack.addAt(control, 1);
          break;
        }
        case "tick-selected": {
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
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          menuSelectionStack.addAt(control, 2);
          break;
        }
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
    _applyLastChangeDate: function(value, old) {
      if (value) {
        if ([
          "study",
          "template",
          "tutorial",
          "hypertool",
        ].includes(this.getResourceType())) {
          const dateBy = this.getChildControl("date-by");
          dateBy.set({
            date: value,
            toolTipText: this.tr("Last modified"),
          });
        }
      }
    },

    // overridden
    _applyTrashedAt: function(value) {
      if (value && value.getTime() !== new Date(0).getTime()) {
        if (["study", "template"].includes(this.getResourceType())) {
          const dateBy = this.getChildControl("date-by");
          dateBy.set({
            date: value,
            toolTipText: this.tr("Deleted"),
          });
        }
      }
    },

    // overridden
    _applyTrashedBy: function(gid) {
      if (gid) {
        if (["study", "template"].includes(this.getResourceType())) {
          const dateBy = this.getChildControl("date-by");
          dateBy.setGroupId(gid);
        }
      }
    },

    __createOwner: function(label) {
      if (label === osparc.auth.Data.getInstance().getEmail()) {
        const resourceAlias = osparc.product.Utils.resourceTypeToAlias(this.getResourceType(), {firstUpperCase: true});
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
        const maxTags = 2;
        const tagsContainer = this.getChildControl("tags");
        tagsContainer.setVisibility(tags.length ? "visible" : "excluded");
        tagsContainer.removeAll();
        for (let i=0; i<tags.length && i<maxTags; i++) {
          const tag = tags[i];
          const tagUI = new osparc.ui.basic.Tag(tag, "searchBarFilter");
          tagUI.set({
            font: "text-12",
            toolTipText: this.tr("Click to filter by this Tag")
          });
          tagUI.addListener("tap", () => this.fireDataEvent("tagClicked", tag));
          tagsContainer.add(tagUI);
        }
        if (tags.length > maxTags) {
          const moreButton = new qx.ui.basic.Label(this.tr("More...")).set({
            font: "text-12",
            backgroundColor: "strong-main",
            appearance: "tag",
          });
          tagsContainer.add(moreButton);
        }
      }
    },
  }
});
