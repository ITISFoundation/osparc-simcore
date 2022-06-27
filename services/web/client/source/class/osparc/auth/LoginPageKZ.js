qx.Class.define("osparc.auth.LoginPageKZ", {
  extend: osparc.auth.LoginPage,

  members: {
    __container: null,

    _getLogoWPlatform: function() {
      const container = this.__container = new qx.ui.container.Stack();
      [
        "osparc/kz_1.jpg",
        "osparc/kz_2.jpg",
        "osparc/kz_3.png",
        "osparc/kz_4.png"
      ].forEach((src, i) => {
        const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
        layout.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
        const image = new qx.ui.basic.Image(src).set({
          allowShrinkX: true,
          allowShrinkY: true,
          width: 300,
          height: 150,
          scale: true
        });
        image.addListener("tap", () => this.__showNext(i));
        layout.add(image);
        layout.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
        container.add(layout);
      });
      return container;
    },

    __showNext: function(currentIdx) {
      const nextIdx = currentIdx === 3 ? 0 : currentIdx+1;
      this.__container.setSelection([this.__container.getSelectables()[nextIdx]]);
    }
  }
});
