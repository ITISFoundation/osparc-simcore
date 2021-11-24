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

    this.addListener("changeValue", this.__itemSelected, this);
  },

  events: {
    "updateQualityStudy": "qx.event.type.Data",
    "updateQualityTemplate": "qx.event.type.Data",
    "updateQualityService": "qx.event.type.Data"
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
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.LOCK_STATUS);
          break;
        case "permission-icon": {
          control = new qx.ui.basic.Image().set({
            minWidth: 50
          });
          control.exclude();
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.PERMISSION);
          break;
        }
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 3).set({
            alignY: "middle"
          })).set({
            alignY: "middle",
            anonymous: true,
            maxWidth: 100
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.TAGS);
          break;
        case "shared-icon": {
          control = new qx.ui.basic.Image().set({
            minWidth: 50,
            alignY: "middle"
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.SHARED);
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
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.LAST_CHANGE);
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
          this._addAt(tsrLayout, osparc.dashboard.ListButtonBase.POS.TSR);
          break;
        }
        case "ui-mode":
          control = new qx.ui.basic.Image().set({
            minWidth: 20,
            alignY: "middle"
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.UI_MODE);
          break;
        case "menu-selection-stack":
          control = new qx.ui.container.Stack().set({
            minWidth: this.self().MENU_BTN_WIDTH,
            minHeight: this.self().MENU_BTN_WIDTH,
            alignY: "middle"
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.OPTIONS);
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

        const store = osparc.store.Store.getInstance();
        Promise.all([
          store.getGroupsAll(),
          store.getVisibleMembers(),
          store.getGroupsOrganizations()
        ])
          .then(values => {
            const all = values[0];
            const orgMembs = [];
            const orgMembers = values[1];
            for (const gid of Object.keys(orgMembers)) {
              orgMembs.push(orgMembers[gid]);
            }
            const orgs = values.length === 3 ? values[2] : [];
            const groups = [orgMembs, orgs, [all]];
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
          const tagUI = new osparc.ui.basic.Tag(tag.name, tag.color, "sideSearchFilter").set({
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
    },

    _applyState: function(state) {
      const locked = ("locked" in state) ? state["locked"]["value"] : false;
      this.setLocked(locked);
      if (locked) {
        this.__setLockedStatus(state["locked"]);
      }
    },

    __setLockedStatus: function(lockedStatus) {
      const status = lockedStatus["status"];
      const owner = lockedStatus["owner"];
      const lock = this.getChildControl("lock-status");
      const lockImage = this.getChildControl("lock-status").getChildControl("image");
      let toolTipText = osparc.utils.Utils.firstsUp(owner["first_name"], owner["last_name"]);
      let source = null;
      switch (status) {
        case "CLOSING":
          source = "@FontAwesome5Solid/key/24";
          toolTipText += this.tr(" is closing it...");
          break;
        case "CLONING":
          source = "@FontAwesome5Solid/clone/24";
          toolTipText += this.tr(" is cloning it...");
          break;
        case "EXPORTING":
          source = osparc.component.task.Export.EXPORT_ICON+"/24";
          toolTipText += this.tr(" is exporting it...");
          break;
        case "OPENING":
          source = "@FontAwesome5Solid/key/24";
          toolTipText += this.tr(" is opening it...");
          break;
        case "OPENED":
          source = "@FontAwesome5Solid/lock/24";
          toolTipText += this.tr(" is using it.");
          break;
        default:
          source = "@FontAwesome5Solid/lock/24";
          break;
      }
      lock.set({
        toolTipText: toolTipText
      });
      lockImage.setSource(source);
    },

    _applyLocked: function(locked) {
      this.__enableCard(!locked);
      this.getChildControl("icon").set({
        visibility: locked ? "excluded" : "visible"
      });
      this.getChildControl("lock-status").set({
        opacity: 1.0,
        visibility: locked ? "visible" : "excluded"
      });
    },

    __enableCard: function(enabled) {
      this.set({
        cursor: enabled ? "pointer" : "not-allowed"
      });

      this._getChildren().forEach(item => {
        item.setOpacity(enabled ? 1.0 : 0.4);
      });
    }
  },

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
