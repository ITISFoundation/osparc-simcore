/**
 * shows all the icons available in the current qooxdoo application
 */

/* global document,iconfont */

qx.Class.define("iconbrowser.Application", {
  extend: qx.application.Standalone,

  members: {
    main: function() {
      this.base(arguments);
      if (qx.core.Environment.get("qx.debug")) {
        // support native logging capabilities, e.g. Firebug for Firefox
        qx.log.appender.Native;
      }
      // dummy call to the inconfont class which will trigger the compiler to copy the
      // font files to the output class.
      // you could also explicitly include the class in the compile.json file

      // iconfont.fontawesome5.Load;

      let copy = document.createElement("input");
      document.body.appendChild(copy);
      // Document is the application root
      let iconDb = {};
      for (let key in qx.$$resources) {
        let re = key.match(/^@([^/]+)\/([^/]+)/);
        if (!re) {
          continue;
        }
        if (!iconDb[re[1]]) {
          iconDb[re[1]] = [];
        }
        iconDb[re[1]].push({
          handle: key,
          name: re[2]
        });
      }

      var doc = this.getRoot();
      var scroll = new qx.ui.container.Scroll().set({
        padding: [20,20,20,20]
      });
      doc.add(scroll, {
        top: 0,
        left: 0,
        right: 0,
        bottom: 0
      });
      var vbox = new qx.ui.container.Composite(new qx.ui.layout.VBox(30));
      scroll.add(vbox);
      for (let font in iconDb) {
        let list = new qx.ui.container.Composite(new qx.ui.layout.Flow());
        vbox.add(list);
        let label = new qx.ui.basic.Label(font).set({font: new qx.bom.Font(30)});
        label.setWidth(80*Math.ceil((label.getSizeHint().width+10.0)/80.0));
        list.add(label);
        iconDb[font].forEach(function(item) {
          let img = new qx.ui.form.Button(null, item.handle + "/40").set({
            toolTipText: item.name + " - click to copy",
            minWidth: 80,
            minHeight: 80
          });
          img.addListener("click", function() {
            copy.value = item.handle;
            copy.select();
            document.execCommand("copy");
          },this);
          list.add(img);
        });
      }
    }
  }
});
