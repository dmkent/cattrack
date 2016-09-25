import { join } from 'path';

import { SeedConfig } from './seed.config';

/**
 * This class extends the basic seed configuration, allowing for project specific overrides. A few examples can be found
 * below.
 */
export class ProjectConfig extends SeedConfig {

  PROJECT_TASKS_DIR = join(process.cwd(), this.TOOLS_DIR, 'tasks', 'project');

  constructor() {
    super();
    this.APP_TITLE = 'CatTrack';

    /* Enable typeless compiler runs (faster) between typed compiler runs. */
    // this.TYPED_COMPILE_INTERVAL = 5;

    // Add `NPM` third-party libraries to be injected/bundled.
    this.NPM_DEPENDENCIES = [
      ...this.NPM_DEPENDENCIES,
      //{src: 'jquery/dist/jquery.min.js', inject: 'libs'},
      //{src: 'ng2-uploader/ng2-uploader.js', inject: 'libs'},
      //{src: 'ng2-pagination/index.js', inject: 'libs'}.
    ];

    // Add `local` third-party libraries to be injected/bundled.
    this.APP_ASSETS = [
      ...this.APP_ASSETS,
      // {src: `${this.APP_SRC}/your-path-to-lib/libs/jquery-ui.js`, inject: true, vendor: false}
      // {src: `${this.CSS_SRC}/path-to-lib/test-lib.css`, inject: true, vendor: false},
      {src: 'node_modules/bootstrap/dist/css/bootstrap.min.css', inject: true, vendor: true}
    ];

    /* Add to or override NPM module configurations: */
    // this.mergeObject(this.PLUGIN_CONFIGS['browser-sync'], { ghostMode: false });

    this.mergeObject(this.SYSTEM_CONFIG_DEV.paths, {
      'ng2-uploader': 'node_modules/ng2-uploader',
      'ng2-pagination': 'node_modules/ng2-pagination',
      'jquery': 'node_modules/jquery',
      'moment': 'node_modules/moment'
    });

    this.SYSTEM_CONFIG_DEV.packages['ng2-uploader'] = {
        main: './ng2-uploader.js'
    };

    this.mergeObject(this.SYSTEM_BUILDER_CONFIG.packages, {
      'ng2-uploader': {
        main: './ng2-uploader.js'
      },
      'ng2-pagination': {
        main: './index.js'
      },
      'jquery': {
        format: 'global',
        exports: '$',
        main: './dist/jquery.min',
        defaultExtension: 'js'
      },
      'moment': {
        main: './moment.js'
      }
    });
  }

}
