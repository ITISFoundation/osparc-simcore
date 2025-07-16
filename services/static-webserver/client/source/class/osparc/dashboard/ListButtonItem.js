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
 */

qx.Class.define("osparc.dashboard.ListButtonItem", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function() {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.ITEM);
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
        case "avatar-group":
          control = new osparc.ui.basic.AvatarGroup(24, "right", 100).set({
            paddingTop: 4, // to align it in the middle
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.AVATAR_GROUP
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
        case "date-by":
          control = new osparc.ui.basic.DateAndBy();
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
        case "menu-button": {
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
          control.getContentElement().setStyles({
            "border-radius": `${this.self().MENU_BTN_DIMENSIONS / 2}px`
          });
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          menuSelectionStack.addAt(control, 1);
          break;
        }
        case "tick-selected": {
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
          const menuSelectionStack = this.getChildControl("menu-selection-stack");
          menuSelectionStack.addAt(control, 2);
          break;
        }
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

    _applyOwner: function(value, old) {
      const label = this.getChildControl("owner");
      const user = this.__createOwner(value);
      label.setValue(user);

      // remove this, testing purposes
      if (osparc.utils.DisabledPlugins.isSimultaneousAccessEnabled() && this.getResourceType() === "study") {
        const avatarGroup = this.getChildControl("avatar-group");
        const allUsers = [
          { name: "Alice", avatar: "https://i.pravatar.cc/150?img=1" },
          { name: "Bob", avatar: "https://i.pravatar.cc/150?img=2" },
          { name: "Charlie", avatar: "https://i.pravatar.cc/150?img=3" },
          { name: "Dana", avatar: "https://i.pravatar.cc/150?img=4" },
          { name: "Eve", avatar: "https://i.pravatar.cc/150?img=5" },
          { name: "Frank", avatar: "https://i.pravatar.cc/150?img=6" },
        ];
        // Random number of users between 1 and 6
        const randomCount = Math.floor(Math.random() * 6) + 1;
        // Shuffle the array and take the first randomCount users
        const shuffled = allUsers.sort(() => 0.5 - Math.random());
        const randomUsers = shuffled.slice(0, randomCount);
        avatarGroup.setUsers(randomUsers);
      }

      this.__makeItemResponsive(label);
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
        const maxTags = 2;
        const tagsContainer = this.getChildControl("tags");
        tagsContainer.removeAll();
        for (let i=0; i<=tags.length && i<maxTags; i++) {
          const tag = tags[i];
          const tagUI = new osparc.ui.basic.Tag(tag, "searchBarFilter");
          tagUI.set({
            alignY: "middle",
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
  }
});
