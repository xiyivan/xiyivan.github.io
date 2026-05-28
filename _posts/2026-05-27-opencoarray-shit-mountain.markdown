---
layout: post
title:  "opencoarray吐槽向"
date:   2026-05-27 22:03:00 0100
categories: [tech]
---

今天在尝试并行计算，需要用到opencoarray。原本计划使用开源链gfortran + openmpi + opencoarray. 在安装aur中的opencoarray时发现 opencoarray 在 openmpi V15 后不再支持openmpi，因为openmpi 无法满足全局统一ID的需求 [open-mpi issue](https://github.com/open-mpi/ompi/issues/13385). 于是转向 mpich（不知为何还满足这个特性）。编译并安装mpich后发现 mpich的可执行文件都放在了/opt/mpich/bin/ 而不是/usr/bin/,导致[opencoarrays-mpich-git\|aur](https://aur.archlinux.org/packages/opencoarrays-mpich-git)无法自动化安装。于是转而从github源码开始编译并直接使用`FC=mpif90`制定mpich。同时这个位置导致cafrun无法找到mpiexec让我又重新编译了一下（～——～）。

令人吐槽的点
- opencoarray一直架在一个并非mpi协议规定的特性上
- mpich 非标准目录结构
- opencoarray的古早CMakeList

P.S. 而且为什么sublime的fortran plugin需要自己下载并编译而不在官方包管理器里啊。