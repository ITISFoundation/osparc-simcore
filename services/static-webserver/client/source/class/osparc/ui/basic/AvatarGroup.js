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


qx.Class.define("osparc.ui.basic.AvatarGroup", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.set({
      decorator: null,
      padding: 0,
      backgroundColor: null,
    });
    this._setLayout(new qx.ui.layout.HBox());

    this.__avatarSize = 30;
    this.__maxVisible = 5;
    this.__users = [
      { name: "Alice", avatar: "https://i.pravatar.cc/150?img=1" },
      { name: "Bob", avatar: "https://i.pravatar.cc/150?img=2" },
      { name: "Charlie", avatar: "https://i.pravatar.cc/150?img=3" },
      { name: "Dana", avatar: "https://i.pravatar.cc/150?img=4" },
      { name: "Eve", avatar: "https://i.pravatar.cc/150?img=5" },
      { name: "Frank", avatar: "https://i.pravatar.cc/150?img=6" },
    ];
    this.__avatars = [];

    this.__buildAvatars();

    // Hover state handling
    this.addListener("mouseover", this.__expand, this);
    this.addListener("mouseout", this.__collapse, this);
  },

  members: {
    __avatarSize: null,
    __maxVisible: null,
    __users: null,
    __avatars: null,

    __buildAvatars() {
      const overlap = Math.floor(this.__avatarSize * 0.5); // 50% overlap
      const overlapPx = `-${overlap}px`;
      const usersToShow = this.__users.slice(0, this.__maxVisible);

      usersToShow.forEach((user, index) => {
        const avatar = new qx.ui.basic.Image(user.avatar);
        avatar.set({
          width: this.__avatarSize,
          height: this.__avatarSize,
          scale: true,
          toolTipText: user.name,
        });

        avatar.getContentElement().setStyles({
          borderRadius: "50%",
          border: "1px solid gray",
          boxShadow: "0 0 0 1px rgba(0,0,0,0.1)",
          marginLeft: index === 0 ? "0px" : overlapPx,
          transition: "margin 0.3s ease",
        });

        avatar.setZIndex(index);
        this.__avatars.push(avatar);
        this._add(avatar);
      });

      if (this.__users.length > this.__maxVisible) {
        const remaining = this.__users.length - this.__maxVisible;
        const label = new qx.ui.basic.Label("+" + remaining);
        label.set({
          width: this.__avatarSize,
          height: this.__avatarSize,
          textAlign: "center",
          backgroundColor: "#ddd",
          font: "bold",
          toolTipText: `${remaining} more`,
        });

        label.getContentElement().setStyles({
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          fontWeight: "bold",
          fontSize: "0.8em",
          borderRadius: "50%",
          border: "1px solid gray",
          boxShadow: "0 0 0 1px rgba(0,0,0,0.1)",
          marginLeft: overlapPx,
          transition: "margin 0.3s ease"
        });

        label.setZIndex(usersToShow.length);
        this.__avatars.push(label);
        this._add(label);
      }
    },

    __expand() {
      const count = this.__avatars.length;
      this.__avatars.forEach((avatar, index) => {
        avatar.getContentElement().setStyle("marginLeft", "8px");
        avatar.setZIndex(count - index);
      });
    },

    __collapse() {
      const overlap = Math.floor(this.__avatarSize * 0.5);
      this.__avatars.forEach((avatar, index) => {
        const margin = index === 0 ? "0px" : `-${overlap}px`;
        avatar.getContentElement().setStyle("marginLeft", margin);
        avatar.setZIndex(index);
      });
    },
  },
});
