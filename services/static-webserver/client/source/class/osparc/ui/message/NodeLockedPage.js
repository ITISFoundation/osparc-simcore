/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * The locked page
 *
 * -----------------------
 * |                     |
 * |    service logo     |
 * |   locked/unlocked   |
 * |    - who is in      |
 * |                     |
 * -----------------------
 *
 */
qx.Class.define("osparc.ui.message.NodeLockedPage", {
  extend: osparc.ui.message.Loading,


  construct: function() {
    this.base(arguments);

    this.__addActionsLayout();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      event: "changeNode",
      apply: "__applyNode",
    },
  },

  members: {
    __avatarGroup: null,

    __applyNode: function(node) {
      const thumbnail = node.getMetadata()["thumbnail"];
      if (thumbnail) {
        this.setLogo(thumbnail);
      }

      const lockState = node.getStatus().getLockState();

      lockState.addListener("changeLocked", this.__lockedChanged, this);
      this.__lockedChanged();

      lockState.addListener("currentUserGroupIds", this.__currentUserGroupIdsChanged, this);
      this.__currentUserGroupIdsChanged();
    },

    __addActionsLayout: function() {
      const actionsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      }));

      const conversationButton = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        toolTipText: this.tr("Conversations"),
        icon: "@FontAwesome5Solid/comments/16",
      });
      conversationButton.addListener("execute", () => {
        if (this.getNode()) {
          const study = this.getNode().getStudy();
          osparc.study.Conversations.popUpInWindow(study.serialize());
        }
      });
      actionsLayout.add(conversationButton);

      const avatarGroup = this.__avatarGroup = new osparc.ui.basic.AvatarGroup(26, "left", 50).set({
        hideMyself: true,
        alignX: "center",
      });
      actionsLayout.add(avatarGroup);
      this.addWidgetToMessages(actionsLayout);
    },

    __lockedChanged: function() {
      const lockState = this.getNode().getStatus().getLockState();
      if (lockState.isLocked()) {
        this._setHeaderIcon("@FontAwesome5Solid/lock/20");
        this._setHeaderTitle(this.tr("The application is being used"));
      } else {
        this._setHeaderIcon("@FontAwesome5Solid/lock-open/20");
        this._setHeaderTitle(this.tr("The application is not being used"));
      }
    },

    __currentUserGroupIdsChanged: function() {
      const lockState = this.getNode().getStatus().getLockState();
      const currentUserGroupIds = lockState.getCurrentUserGroupIds();
      this.__avatarGroup.setUserGroupIds(currentUserGroupIds);
    },
  }
});
