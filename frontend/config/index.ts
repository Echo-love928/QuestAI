import { defineConfig, type UserConfigExport } from '@tarojs/cli'
import path from 'node:path'

const config: UserConfigExport = {
  projectName: 'AI闯关学习',
  date: '2026-08-31',
  designWidth: 390,
  deviceRatio: {
    390: 2
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  alias: {
    '@': path.resolve(__dirname, '..', 'src')
  },
  plugins: [],
  defineConstants: {
    'process.env.TARO_APP_API_BASE': JSON.stringify(
      process.env.TARO_APP_API_BASE || 'http://127.0.0.1:8000/api/v1'
    )
  },
  copy: {
    patterns: [],
    options: {}
  },
  framework: 'react',
  compiler: 'webpack5',
  cache: {
    enable: true
  },
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
        config: {}
      },
      url: {
        enable: true,
        config: {
          limit: 1024
        }
      },
      cssModules: {
        enable: false,
        config: {
          namingPattern: 'module',
          generateScopedName: '[name]__[local]___[hash:base64:5]'
        }
      }
    }
  },
  h5: {}
}

export default defineConfig(config)
