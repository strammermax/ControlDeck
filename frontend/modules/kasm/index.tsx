"use client";
import {AppLaunch} from "../../components/app-launch";
import type {ModuleViewProps} from "../contracts";
export function View({csrfToken}:ModuleViewProps) {return <AppLaunch moduleId="kasm" title="Kasm" csrfToken={csrfToken}/>;}
export function Settings() {return <p>Deze module gebruikt de centraal ingerichte Kasm-aanmelding. Je hoeft hier geen wachtwoord of API-sleutel in te vullen.</p>;}
