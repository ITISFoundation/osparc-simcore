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

    this._setLayout(new qx.ui.layout.HBox());

    this.__users = [
      { name: "Alice", avatar: "https://i.pravatar.cc/150?img=1" },
      { name: "Bob", avatar: "https://i.pravatar.cc/150?img=2" },
      { name: "Charlie", avatar: "https://i.pravatar.cc/150?img=3" },
      { name: "Dana", avatar: "https://i.pravatar.cc/150?img=4" },
      { name: "Eve", avatar: "https://i.pravatar.cc/150?img=5" },
      { name: "Frank", avatar: "https://i.pravatar.cc/150?img=6" },
    ];
    this.__maxVisible = 5;
    this.__avatars = [];

    this.__buildAvatars();

    // Hover state handling
    this.addListener("mouseover", this.__expand, this);
    this.addListener("mouseout", this.__collapse, this);
  },

  members: {
    __avatars: null,
    __users: null,
    __maxVisible: null,

    __buildAvatars() {
      const usersToShow = this.__users.slice(0, this.__maxVisible);

      usersToShow.forEach((user, index) => {
        const avatar = new qx.ui.basic.Image(user.avatar);
        avatar.set({
          width: 40,
          height: 40,
          scale: true,
          decorator: "main", // You can use or define a circle decorator
          toolTipText: user.name,
        });

        avatar.getContentElement().setStyles({
          borderRadius: "50%",
          border: "2px solid white",
          boxShadow: "0 0 0 1px rgba(0,0,0,0.1)",
          marginLeft: index === 0 ? "0px" : "-12px",
          transition: "margin 0.3s ease",
        });

        this.__avatars.push(avatar);
        this._add(avatar);
      });

      if (this.__users.length > this.__maxVisible) {
        const remaining = this.__users.length - this.__maxVisible;
        const label = new qx.ui.basic.Label("+" + remaining);
        label.set({
          width: 40,
          height: 40,
          textAlign: "center",
          backgroundColor: "#ddd",
          font: "bold",
          allowGrowX: false,
          allowGrowY: false,
          toolTipText: `${remaining} more`,
        });

        label.getContentElement().setStyles({
          lineHeight: "40px",
          borderRadius: "50%",
          border: "2px solid white",
          boxShadow: "0 0 0 1px rgba(0,0,0,0.1)",
          marginLeft: "-12px"
        });

        this.__avatars.push(label);
        this._add(label);
      }
    },

    __expand() {
      this.__avatars.forEach(avatar => {
        avatar.getContentElement().setStyle("marginLeft", "8px");
        avatar.setZIndex(1);
      });
    },

    __collapse() {
      this.__avatars.forEach((avatar, index) => {
        avatar.getContentElement().setStyle("marginLeft", index === 0 ? "0px" : "-12px");
        avatar.setZIndex(index);
      });
    },
  },
});
