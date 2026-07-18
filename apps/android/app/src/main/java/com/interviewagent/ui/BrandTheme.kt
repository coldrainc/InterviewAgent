package com.interviewagent.ui

import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

object BrandColors {
    val Background = Color(0xFFEEF4F1)
    val SurfaceSoft = Color(0xFFF7FAF8)
    val Text = Color(0xFF14251F)
    val Muted = Color(0xFF64756F)
    val Primary = Color(0xFF2F63E8)
    val PrimaryStrong = Color(0xFF234ED1)
    val Teal = Color(0xFF0F8F8F)
    val Success = Color(0xFF16A673)
    val Warning = Color(0xFFC77918)
    val Danger = Color(0xFFD43B3B)
}

val BrandColorScheme = lightColorScheme(
    primary = BrandColors.Primary,
    onPrimary = Color.White,
    secondary = BrandColors.Teal,
    background = BrandColors.Background,
    surface = Color.White,
    onSurface = BrandColors.Text,
    error = BrandColors.Danger
)
