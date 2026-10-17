/** Значения формы запроса доступа; honeypot (website) заполняют только боты. */
export interface RequestAccessFormValues {
  email: string;
  display_name: string;
  purpose: string;
  consent: boolean;
  website?: string;
}
