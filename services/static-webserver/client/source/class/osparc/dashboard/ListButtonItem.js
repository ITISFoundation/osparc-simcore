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
        case "permission-icon": {
          control = new qx.ui.basic.Image().set({
            minWidth: 50
          });
          control.exclude();
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.PERMISSION
          });
          break;
        }
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
        case "shared-icon": {
          control = new qx.ui.basic.Image().set({
            minWidth: 50,
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.SHARED
          });
          break;
        }
        case "last-change": {
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
        }
        case "tsr-rating": {
          const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2).set({
            alignY: "middle"
          })).set({
            toolTipText: this.tr("Ten Simple Rules"),
            minWidth: 85
          });
          const tsrLabel = new qx.ui.basic.Label(this.tr("TSR:"));
          tsrLayout.add(tsrLabel);
          control = new osparc.ui.basic.StarsRating();
          tsrLayout.add(control);
          this._add(tsrLayout, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.TSR
          });
          break;
        }
        case "ui-mode":
          control = new qx.ui.basic.Image().set({
            minWidth: 20,
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.UI_MODE
          });
          break;
        case "hits-service": {
          control = new qx.ui.basic.Label().set({
            alignY: "middle",
            toolTipText: this.tr("Number of times it was instantiated")
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.HITS
          });
          break;
        }
        case "update-study":
          control = new qx.ui.basic.Image().set({
            minWidth: 20,
            alignY: "middle",
            source: "@MaterialIcons/update/18",
            visibility: "excluded"
          });
          this._add(control, {
            row: 0,
            column: osparc.dashboard.ListButtonBase.POS.UPDATE_STUDY
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

    _applyAccessRights: function(value, old) {
      if (value && Object.keys(value).length) {
        const sharedIcon = this.getChildControl("shared-icon");
        sharedIcon.addListener("tap", e => {
          e.stopPropagation();
          this._openAccessRights();
        }, this);
        sharedIcon.addListener("pointerdown", e => e.stopPropagation());

        const store = osparc.store.Store.getInstance();
        Promise.all([
          store.getGroupEveryone(),
          store.getVisibleMembers(),
          store.getGroupsOrganizations()
        ])
          .then(values => {
            const everyone = values[0];
            const orgMembs = [];
            const orgMembers = values[1];
            for (const gid of Object.keys(orgMembers)) {
              orgMembs.push(orgMembers[gid]);
            }
            const orgs = values.length === 3 ? values[2] : [];
            const groups = [orgMembs, orgs, [everyone]];
            this.__setSharedIcon(sharedIcon, value, groups);
          });

        if (this.isResourceType("study")) {
          this._setStudyPermissions(value);
        }
      }
    },

    __setSharedIcon: function(image, value, groups) {
      let sharedGrps = [];
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      for (let i=0; i<groups.length; i++) {
        const sharedGrp = [];
        const gids = Object.keys(value);
        for (let j=0; j<gids.length; j++) {
          const gid = parseInt(gids[j]);
          if (this.isResourceType("study") && (gid === myGroupId)) {
            continue;
          }
          const grp = groups[i].find(group => group["gid"] === gid);
          if (grp) {
            sharedGrp.push(grp);
          }
        }
        if (sharedGrp.length === 0) {
          continue;
        } else {
          sharedGrps = sharedGrps.concat(sharedGrp);
        }
        switch (i) {
          case 0:
            image.setSource(osparc.dashboard.CardBase.SHARED_USER);
            break;
          case 1:
            image.setSource(osparc.dashboard.CardBase.SHARED_ORGS);
            break;
          case 2:
            image.setSource(osparc.dashboard.CardBase.SHARED_ALL);
            break;
        }
      }

      if (sharedGrps.length === 0) {
        image.setVisibility("excluded");
        return;
      }

      const sharedGrpLabels = [];
      const maxItems = 6;
      for (let i=0; i<sharedGrps.length; i++) {
        if (i > maxItems) {
          sharedGrpLabels.push("...");
          break;
        }
        const sharedGrpLabel = sharedGrps[i]["label"];
        if (!sharedGrpLabels.includes(sharedGrpLabel)) {
          sharedGrpLabels.push(sharedGrpLabel);
        }
      }
      const hintText = sharedGrpLabels.join("<br>");
      const hint = new osparc.ui.hint.Hint(image, hintText);
      image.addListener("mouseover", () => hint.show(), this);
      image.addListener("mouseout", () => hint.exclude(), this);
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
      }
      menuButton.setVisibility(value ? "visible" : "excluded");
    }
  }
});
